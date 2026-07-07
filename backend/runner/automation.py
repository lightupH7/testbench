from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.api.schemas import ManualExecuteRequest
from backend.db.config import DB_PATH
from backend.drivers.base import DriverResult
from backend.drivers.uart_driver import UartDriver
from backend.services.manual import execute_manual_action
from backend.services.terminal_monitor import terminal_broadcast_hub


DEFAULT_AUTOMATION_CASE_NAME = "program_lowrisc_and_uart_echo_1"
DEFAULT_AUTOMATION_CASE_CONFIG: dict[str, Any] = {
    "bit_file": "artifacts/bitstreams/lowrisc_systems_chip.bit",
    "elf_file": "artifacts/firmware/testbench_case1.elf",
    "vivado_path": "vivado",
    "hw_server_url": "localhost:3121",
    "device": "RISC-V",
    "interface": "JTAG",
    "speed": 4000,
    "program_timeout": 120,
    "uart_port": "",
    "uart_baudrate": 115200,
    "uart_timeout": 10,
    "uart_send": "1",
    "uart_expect": "1",
}


async def ensure_default_automation_case() -> None:
    _ensure_default_automation_case_sync()


def list_test_cases_sync() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            select id, name, type, description, config_json, enabled, created_at, updated_at
            from test_cases
            order by id
            """,
        ).fetchall()
    return [_case_from_row(row) for row in rows]


def list_runs_sync() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            select id, plan_id, hardware_profile_id, name, status, result,
                   selected_case_ids_json, started_at, ended_at, created_at
            from test_runs
            order by id desc
            """,
        ).fetchall()
    return [_run_from_row(row) for row in rows]


def create_run_sync(
    *,
    name: str | None,
    plan_id: int | None,
    hardware_profile_id: int | None,
    selected_case_ids: list[int],
    config_overrides: dict[str, Any],
) -> dict[str, Any]:
    now = _now()
    payload = {"case_ids": selected_case_ids, "config_overrides": config_overrides}
    with _connect() as connection:
        rows = connection.execute(
            "select id from test_cases where enabled = 1 and id in (%s)"
            % ",".join("?" for _ in selected_case_ids),
            selected_case_ids,
        ).fetchall()
        found_case_ids = {int(row["id"]) for row in rows}
        missing_case_ids = [
            case_id for case_id in selected_case_ids if case_id not in found_case_ids
        ]
        if missing_case_ids:
            raise ValueError(json.dumps({"case_ids": missing_case_ids}))

        cursor = connection.execute(
            """
            insert into test_runs (
                plan_id, hardware_profile_id, name, status, result,
                selected_case_ids_json, started_at, ended_at, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                hardware_profile_id,
                name,
                "pending",
                None,
                json.dumps(payload),
                None,
                None,
                now,
            ),
        )
        connection.commit()
        run_id = int(cursor.lastrowid)
    run = get_run_sync(run_id)
    if run is None:
        raise RuntimeError("created test run could not be loaded")
    return run


def get_run_sync(run_id: int) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            """
            select id, plan_id, hardware_profile_id, name, status, result,
                   selected_case_ids_json, started_at, ended_at, created_at
            from test_runs
            where id = ?
            """,
            (run_id,),
        ).fetchone()
    return _run_from_row(row) if row is not None else None


def list_case_results_sync(run_id: int) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            select id, run_id, case_id, case_name, case_type, status, result, log,
                   started_at, ended_at, created_at
            from test_case_results
            where run_id = ?
            order by id
            """,
            (run_id,),
        ).fetchall()
    return [_case_result_from_row(row) for row in rows]


def list_step_results_sync(run_id: int) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            select id, run_id, name, type, status, result, log,
                   started_at, ended_at, created_at
            from test_step_results
            where run_id = ?
            order by id
            """,
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_logs_sync(run_id: int) -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute(
            """
            select id, run_id, case_result_id, level, source, message, created_at
            from test_logs
            where run_id = ?
            order by id
            """,
            (run_id,),
        ).fetchall()
    return [dict(row) for row in rows]


async def run_test_run(run_id: int) -> None:
    await _update_run(run_id, status="running", result=None, started_at=_now(), ended_at=None)
    await _log(run_id, None, "INFO", "runner", f"Test run {run_id} started.")

    try:
        run = get_run_sync(run_id)
        cases = _load_selected_cases_sync(run)
        if not cases:
            await _log(run_id, None, "ERROR", "runner", "No enabled test cases selected.")
            await _update_run(run_id, status="failed", result="error", ended_at=_now())
            return

        failed = False
        for case in cases:
            case_result_id = _create_case_result_sync(run_id, case)
            await _log(
                run_id,
                case_result_id,
                "INFO",
                case["name"],
                f"Case {case['name']} started.",
            )
            result = await _execute_case(run_id, run, case, case_result_id)
            if not result:
                failed = True
                break

        await _update_run(
            run_id,
            status="completed",
            result="fail" if failed else "pass",
            ended_at=_now(),
        )
        completed = get_run_sync(run_id) or {}
        await _log(
            run_id,
            None,
            "INFO",
            "runner",
            f"Test run {run_id} completed with result {completed.get('result')}.",
        )
    except Exception as exc:  # noqa: BLE001
        await _log(run_id, None, "ERROR", "runner", f"Runner crashed: {exc}")
        await _update_run(run_id, status="failed", result="error", ended_at=_now())


async def _execute_case(
    run_id: int,
    run: dict[str, Any] | None,
    case: dict[str, Any],
    case_result_id: int,
) -> bool:
    if case["type"] != "program_lowrisc_uart_echo":
        message = f"Unsupported test case type: {case['type']}"
        _finish_case_result_sync(case_result_id, "completed", "error", message)
        await _log(run_id, case_result_id, "ERROR", case["name"], message)
        return False

    config = _merged_config(case["config_json"], run)
    required = _missing_required_config(config, ["bit_file", "elf_file", "uart_port"])
    if required:
        message = f"Missing required config: {', '.join(required)}"
        _finish_case_result_sync(case_result_id, "completed", "error", message)
        await _log(run_id, case_result_id, "ERROR", case["name"], message)
        return False

    if not await _program_files(run_id, case_result_id, config):
        _finish_case_result_sync(case_result_id, "completed", "fail", "Programming failed.")
        return False

    uart_ok = await _uart_echo_check(run_id, case_result_id, config)
    message = (
        "Programming succeeded and expected UART response was observed."
        if uart_ok
        else "Programming succeeded but expected UART response was not observed."
    )
    _finish_case_result_sync(case_result_id, "completed", "pass" if uart_ok else "fail", message)
    return uart_ok


async def _program_files(
    run_id: int,
    case_result_id: int,
    config: dict[str, Any],
) -> bool:
    step_id = _create_step_sync(run_id, "Program bitstream and ELF", "program_all")
    loop = asyncio.get_running_loop()
    request = ManualExecuteRequest(
        action="program_all",
        bit_file=_path(config["bit_file"]),
        elf_file=_path(config["elf_file"]),
        vivado_path=str(config.get("vivado_path") or "vivado"),
        hw_server_url=_optional_str(config.get("hw_server_url")),
        device=_optional_str(config.get("device")),
        interface=str(config.get("interface") or "JTAG"),
        speed=int(config.get("speed") or 4000),
        timeout=int(config.get("program_timeout") or 120),
    )

    def emit(label: str, channel: str, chunk: str) -> None:
        asyncio.run_coroutine_threadsafe(
            _log(
                run_id,
                case_result_id,
                "INFO" if channel == "stdout" else "ERROR",
                label,
                chunk,
            ),
            loop,
        )

    result = await asyncio.to_thread(execute_manual_action, request, emit)
    _finish_step_sync(step_id, result)
    await _log_driver_result(run_id, case_result_id, "program_all", result)
    return result.success


async def _uart_echo_check(
    run_id: int,
    case_result_id: int,
    config: dict[str, Any],
) -> bool:
    step_id = _create_step_sync(run_id, "UART send and expect ASCII 1", "uart_echo")
    driver = UartDriver(
        config={
            "port": str(config["uart_port"]),
            "baudrate": int(config.get("uart_baudrate") or 115200),
            "timeout": 0.05,
            "write_timeout": 1.0,
            "read_until_timeout": float(config.get("uart_timeout") or 10),
        },
    )

    try:
        connect_result = await asyncio.to_thread(driver.connect)
        await _log_driver_result(run_id, case_result_id, "uart_connect", connect_result)
        if not connect_result.success:
            _finish_step_sync(step_id, connect_result)
            return False

        await asyncio.to_thread(driver.reset_input_buffer)
        write_result = await asyncio.to_thread(
            driver.write,
            str(config.get("uart_send") or "1"),
            "ascii",
            False,
        )
        await _log_driver_result(run_id, case_result_id, "uart_write", write_result)
        if not write_result.success:
            _finish_step_sync(step_id, write_result)
            return False

        read_result = await asyncio.to_thread(
            driver.read_until,
            str(config.get("uart_expect") or "1"),
            float(config.get("uart_timeout") or 10),
            "ascii",
            "replace",
        )
        await _log_driver_result(run_id, case_result_id, "uart_read_until", read_result)
        _finish_step_sync(step_id, read_result)
        return read_result.success
    finally:
        await asyncio.to_thread(driver.close)


def _ensure_default_automation_case_sync() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = _now()
    with _connect() as connection:
        row = connection.execute(
            "select id from test_cases where name = ?",
            (DEFAULT_AUTOMATION_CASE_NAME,),
        ).fetchone()
        if row is not None:
            return
        connection.execute(
            """
            insert into test_cases (
                name, type, description, config_json, enabled, created_at, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                DEFAULT_AUTOMATION_CASE_NAME,
                "program_lowrisc_uart_echo",
                (
                    "Program lowrisc_systems_chip.bit and zephyr-it.elf, send ASCII 1 "
                    "over UART, and pass when ASCII 1 is observed."
                ),
                json.dumps(DEFAULT_AUTOMATION_CASE_CONFIG),
                1,
                now,
                now,
            ),
        )
        connection.commit()


def _load_selected_cases_sync(run: dict[str, Any] | None) -> list[dict[str, Any]]:
    if run is None:
        return []
    payload = _json_loads(run.get("selected_case_ids_json"))
    case_ids = payload.get("case_ids") if isinstance(payload, dict) else []
    if not case_ids:
        return []
    with _connect() as connection:
        rows = connection.execute(
            "select id, name, type, description, config_json, enabled, created_at, updated_at "
            "from test_cases where enabled = 1 and id in (%s)"
            % ",".join("?" for _ in case_ids),
            case_ids,
        ).fetchall()
    by_id = {_case_from_row(row)["id"]: _case_from_row(row) for row in rows}
    return [by_id[case_id] for case_id in case_ids if case_id in by_id]


def _create_case_result_sync(run_id: int, case: dict[str, Any]) -> int:
    with _connect() as connection:
        cursor = connection.execute(
            """
            insert into test_case_results (
                run_id, case_id, case_name, case_type, status, result, log,
                started_at, ended_at, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                case["id"],
                case["name"],
                case["type"],
                "running",
                None,
                None,
                _now(),
                None,
                _now(),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def _finish_case_result_sync(
    case_result_id: int,
    status: str,
    result: str,
    log: str,
) -> None:
    with _connect() as connection:
        connection.execute(
            """
            update test_case_results
            set status = ?, result = ?, log = ?, ended_at = ?
            where id = ?
            """,
            (status, result, log, _now(), case_result_id),
        )
        connection.commit()


def _create_step_sync(run_id: int, name: str, step_type: str) -> int:
    with _connect() as connection:
        cursor = connection.execute(
            """
            insert into test_step_results (
                run_id, name, type, status, result, log, started_at, ended_at, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, name, step_type, "running", None, None, _now(), None, _now()),
        )
        connection.commit()
        return int(cursor.lastrowid)


def _finish_step_sync(step_id: int, result: DriverResult) -> None:
    with _connect() as connection:
        connection.execute(
            """
            update test_step_results
            set status = ?, result = ?, log = ?, ended_at = ?
            where id = ?
            """,
            ("completed", "pass" if result.success else "fail", result.message, _now(), step_id),
        )
        connection.commit()


async def _update_run(run_id: int, **values: Any) -> None:
    if not values:
        return
    keys = list(values)
    assignments = ", ".join(f"{key} = ?" for key in keys)
    with _connect() as connection:
        connection.execute(
            f"update test_runs set {assignments} where id = ?",
            [values[key] for key in keys] + [run_id],
        )
        connection.commit()


async def _log_driver_result(
    run_id: int,
    case_result_id: int | None,
    source: str,
    result: DriverResult,
) -> None:
    level = "INFO" if result.success else "ERROR"
    for message in [result.message, result.stdout, result.stderr]:
        if message:
            await _log(run_id, case_result_id, level, source, str(message))


async def _log(
    run_id: int,
    case_result_id: int | None,
    level: str,
    source: str,
    message: str,
) -> None:
    normalized = message.strip()
    if not normalized:
        return
    with _connect() as connection:
        connection.execute(
            """
            insert into test_logs (run_id, case_result_id, level, source, message, created_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            (run_id, case_result_id, level, source, normalized, _now()),
        )
        connection.commit()
    await terminal_broadcast_hub.broadcast(f"\r\n[{source}] {normalized}\r\n")


def _merged_config(base: dict[str, Any], run: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(base)
    payload = _json_loads(run.get("selected_case_ids_json") if run else None)
    if isinstance(payload, dict) and isinstance(payload.get("config_overrides"), dict):
        merged.update(payload["config_overrides"])
    return merged


def _missing_required_config(config: dict[str, Any], keys: list[str]) -> list[str]:
    return [key for key in keys if not str(config.get(key) or "").strip()]


def _case_from_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["config_json"] = _json_loads(data.get("config_json")) or {}
    data["enabled"] = bool(data["enabled"])
    return data


def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _case_result_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


def _json_loads(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return None
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return None


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, timeout=5)
    connection.row_factory = sqlite3.Row
    return connection


def _path(path_value: Any) -> str:
    path = Path(str(path_value)).expanduser()
    if path.is_absolute():
        return str(path)
    return str(Path.cwd() / path)


def _optional_str(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
