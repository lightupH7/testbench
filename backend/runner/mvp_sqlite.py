from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from backend.db.config import DB_PATH
from backend.db.schema_compat import ensure_mvp_schema
from backend.drivers.base import DriverResult
from backend.runner.step_executor import execute_step


PROFILE_COLUMNS = [
    "name",
    "description",
    "is_default",
    "board_name",
    "board_serial",
    "bit_file",
    "bit_program_channel",
    "elf_file",
    "jlink_serial",
    "jlink_interface",
    "jlink_device",
    "jlink_speed_khz",
    "uart_port",
    "uart_baudrate",
    "uart_bytesize",
    "uart_parity",
    "uart_stopbits",
    "uart_timeout_ms",
    "scope_model",
    "scope_ip",
    "scope_port",
    "scope_channel",
]

ACTIVE_RUN_STATUSES = {"waiting", "running", "stopping"}
FINAL_RUN_STATUSES = {"passed", "failed", "error", "stopped"}
_worker_task: asyncio.Task[None] | None = None
_worker_lock = asyncio.Lock()


def list_profiles() -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute("select * from hardware_profiles order by id").fetchall()
    return [dict(row) for row in rows]


def get_profile(profile_id: int) -> dict[str, Any] | None:
    with _connect() as db:
        row = db.execute("select * from hardware_profiles where id = ?", (profile_id,)).fetchone()
    return dict(row) if row else None


def save_profile(payload: dict[str, Any], profile_id: int | None = None) -> dict[str, Any]:
    now = _now()
    values = [_to_db(payload.get(column)) for column in PROFILE_COLUMNS]
    with _connect() as db:
        if profile_id is None:
            columns = ", ".join([*PROFILE_COLUMNS, "created_at", "updated_at"])
            placeholders = ", ".join("?" for _ in [*PROFILE_COLUMNS, "created_at", "updated_at"])
            cursor = db.execute(
                f"insert into hardware_profiles ({columns}) values ({placeholders})",
                [*values, now, now],
            )
            profile_id = int(cursor.lastrowid)
        else:
            assignments = ", ".join(f"{column} = ?" for column in PROFILE_COLUMNS)
            db.execute(
                f"update hardware_profiles set {assignments}, updated_at = ? where id = ?",
                [*values, now, profile_id],
            )
        db.commit()
    result = get_profile(profile_id)
    if result is None:
        raise ValueError("hardware profile not found")
    return result


def delete_profile(profile_id: int) -> bool:
    with _connect() as db:
        cursor = db.execute("delete from hardware_profiles where id = ?", (profile_id,))
        db.commit()
    return cursor.rowcount > 0


def list_cases() -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute("select * from test_cases order by id").fetchall()
    return [_case_from_row(row) for row in rows]


def get_case(case_id: int) -> dict[str, Any] | None:
    with _connect() as db:
        row = db.execute("select * from test_cases where id = ?", (case_id,)).fetchone()
    return _case_from_row(row) if row else None


def save_case(payload: dict[str, Any], case_id: int | None = None) -> dict[str, Any]:
    now = _now()
    with _connect() as db:
        if case_id is None:
            cursor = db.execute(
                """
                insert into test_cases (name, type, description, config_json, enabled, created_at, updated_at)
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload["name"],
                    "db_steps",
                    payload.get("description"),
                    "{}",
                    int(bool(payload.get("enabled", True))),
                    now,
                    now,
                ),
            )
            case_id = int(cursor.lastrowid)
        else:
            db.execute(
                "update test_cases set name = ?, description = ?, enabled = ?, updated_at = ? where id = ?",
                (
                    payload["name"],
                    payload.get("description"),
                    int(bool(payload.get("enabled", True))),
                    now,
                    case_id,
                ),
            )
        db.commit()
    result = get_case(case_id)
    if result is None:
        raise ValueError("test case not found")
    return result


def delete_case(case_id: int) -> bool:
    with _connect() as db:
        cursor = db.execute("delete from test_cases where id = ?", (case_id,))
        db.commit()
    return cursor.rowcount > 0


def list_steps(case_id: int) -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute(
            "select * from test_steps where case_id = ? order by order_index, id",
            (case_id,),
        ).fetchall()
    return [_step_from_row(row) for row in rows]


def save_step(case_id: int, payload: dict[str, Any], step_id: int | None = None) -> dict[str, Any]:
    now = _now()
    with _connect() as db:
        if step_id is None:
            cursor = db.execute(
                """
                insert into test_steps (
                    case_id, order_index, step_type, name, config_json, expected_json,
                    timeout_ms, continue_on_failure, created_at, updated_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    payload["order_index"],
                    payload["step_type"],
                    payload["name"],
                    json.dumps(payload.get("config_json") or {}),
                    json.dumps(payload.get("expected_json") or {}),
                    payload["timeout_ms"],
                    int(bool(payload.get("continue_on_failure", False))),
                    now,
                    now,
                ),
            )
            step_id = int(cursor.lastrowid)
        else:
            db.execute(
                """
                update test_steps
                set order_index = ?, step_type = ?, name = ?, config_json = ?,
                    expected_json = ?, timeout_ms = ?, continue_on_failure = ?, updated_at = ?
                where id = ?
                """,
                (
                    payload["order_index"],
                    payload["step_type"],
                    payload["name"],
                    json.dumps(payload.get("config_json") or {}),
                    json.dumps(payload.get("expected_json") or {}),
                    payload["timeout_ms"],
                    int(bool(payload.get("continue_on_failure", False))),
                    now,
                    step_id,
                ),
            )
        db.commit()
        row = db.execute("select * from test_steps where id = ?", (step_id,)).fetchone()
    if row is None:
        raise ValueError("test step not found")
    return _step_from_row(row)


def delete_step(step_id: int) -> bool:
    with _connect() as db:
        cursor = db.execute("delete from test_steps where id = ?", (step_id,))
        db.commit()
    return cursor.rowcount > 0


def list_runs() -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute("select * from test_runs order by id desc").fetchall()
    return _attach_queue_positions([_run_from_row(row) for row in rows])


def count_table(table_name: str) -> int:
    allowed = {"hardware_profiles", "test_cases", "test_plans", "test_runs"}
    if table_name not in allowed:
        raise ValueError("unsupported table")
    with _connect() as db:
        row = db.execute(f"select count(*) from {table_name}").fetchone()
    return int(row[0]) if row else 0


def list_test_plans() -> list[dict[str, Any]]:
    with _connect() as db:
        if not _table_exists(db, "test_plans"):
            return []
        rows = db.execute("select * from test_plans order by id").fetchall()
    return [dict(row) for row in rows]


def get_run_detail(run_id: int) -> dict[str, Any] | None:
    with _connect() as db:
        run = db.execute("select * from test_runs where id = ?", (run_id,)).fetchone()
        if run is None:
            return None
        steps = db.execute(
            "select * from test_step_results where run_id = ? order by order_index, id",
            (run_id,),
        ).fetchall()
    payload = _run_from_row(run)
    payload["run_id"] = payload["id"]
    payload["steps"] = [_step_result_from_row(row) for row in steps]
    return _attach_queue_positions([payload])[0]


async def enqueue_run(profile_id: int, case_id: int, name: str | None = None) -> dict[str, Any]:
    profile = get_profile(profile_id)
    test_case = get_case(case_id)
    steps = list_steps(case_id)
    if profile is None:
        raise ValueError("hardware profile not found")
    if test_case is None:
        raise ValueError("test case not found")
    if not test_case["enabled"]:
        raise ValueError("test case is disabled")
    if not steps:
        raise ValueError("test case has no steps")

    started_at = _now()
    case_snapshot = {**test_case, "steps": steps}
    with _connect() as db:
        cursor = db.execute(
            """
            insert into test_runs (
                hardware_profile_id, test_case_id, name, status, result, summary,
                error_message, profile_snapshot_json, case_snapshot_json, started_at, created_at,
                total_steps, completed_steps, progress_percent, cancel_requested
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                case_id,
                name or f"{test_case['name']} @ {started_at}",
                "waiting",
                None,
                "等待执行",
                "",
                json.dumps(profile),
                json.dumps(case_snapshot),
                started_at,
                len(steps),
                0,
                0,
                0,
                started_at,
            ),
        )
        run_id = int(cursor.lastrowid)
        db.commit()
    await ensure_worker_running()
    detail = get_run_detail(run_id)
    if detail is None:
        raise RuntimeError("created test run could not be loaded")
    return detail



async def ensure_worker_running() -> None:
    global _worker_task

    async with _worker_lock:
        if _worker_task is not None and not _worker_task.done():
            return
        _worker_task = asyncio.create_task(_worker_loop())


async def initialize_run_queue() -> None:
    _recover_incomplete_runs()
    if _has_waiting_runs():
        await ensure_worker_running()


async def stop_run(run_id: int) -> dict[str, Any]:
    with _connect() as db:
        run_row = db.execute("select status from test_runs where id = ?", (run_id,)).fetchone()
        if run_row is None:
            raise ValueError("test run not found")
        status = str(run_row["status"])

        if status == "waiting":
            finished_at = _now()
            db.execute(
                """
                update test_runs
                set status = ?, result = ?, summary = ?, error_message = ?, finished_at = ?, ended_at = ?
                where id = ?
                """,
                ("stopped", "stopped", "已手动停止", "任务在等待时被停止", finished_at, finished_at, run_id),
            )
        elif status in {"running", "stopping"}:
            db.execute(
                """
                update test_runs
                set cancel_requested = 1, status = ?, summary = ?
                where id = ?
                """,
                ("stopping", "正在停止", run_id),
            )
        db.commit()

    detail = get_run_detail(run_id)
    if detail is None:
        raise ValueError("test run not found")
    return detail


def _insert_step_result(
    run_id: int,
    step: dict[str, Any],
    result: DriverResult,
    status: str,
    started_at: str,
    finished_at: str,
) -> None:
    with _connect() as db:
        db.execute(
            """
            insert into test_step_results (
                run_id, test_step_id, order_index, step_name, step_type, name, type,
                status, result, message, stdout, stderr, data_json, log,
                started_at, finished_at, ended_at, duration_ms, created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                step["id"],
                step["order_index"],
                step["name"],
                step["step_type"],
                step["name"],
                step["step_type"],
                status,
                "pass" if status == "passed" else status,
                result.message,
                result.stdout,
                result.stderr,
                json.dumps(_json_safe(result.data)),
                result.message,
                started_at,
                finished_at,
                finished_at,
                _duration_ms(started_at, finished_at),
                finished_at,
            ),
        )
        db.commit()


async def _worker_loop() -> None:
    while True:
        run = _next_waiting_run()
        if run is None:
            return
        try:
            await _execute_queued_run(run)
        except Exception as exc:  # noqa: BLE001
            _finish_run(
                int(run["id"]),
                status="error",
                result="error",
                summary="测试异常",
                error_message=str(exc),
            )


def _next_waiting_run() -> dict[str, Any] | None:
    with _connect() as db:
        row = db.execute(
            """
            select * from test_runs
            where status = 'waiting'
            order by created_at, id
            limit 1
            """,
        ).fetchone()
    return _run_from_row(row) if row else None


async def _execute_queued_run(run: dict[str, Any]) -> None:
    profile_id = int(run["hardware_profile_id"])
    case_id = int(run["test_case_id"])
    profile = get_profile(profile_id)
    test_case = get_case(case_id)
    steps = list_steps(case_id)
    if profile is None or test_case is None or not steps:
        _finish_run(
            run["id"],
            status="error",
            result="error",
            summary="测试异常",
            error_message="run dependencies not found",
        )
        return

    started_at = _now()
    with _connect() as db:
        db.execute(
            """
            update test_runs
            set status = ?, summary = ?, started_at = ?, total_steps = ?, completed_steps = ?, progress_percent = ?, current_step_name = ?, cancel_requested = 0
            where id = ?
            """,
            ("running", "测试运行中", started_at, len(steps), 0, 0, None, run["id"]),
        )
        db.commit()

    final_status = "passed"
    summary = "测试通过"
    error_message = ""
    profile_obj = SimpleNamespace(**profile)

    for index, step in enumerate(steps, start=1):
        current = get_run_detail(run["id"])
        if current is not None and current.get("cancel_requested"):
            final_status = "stopped"
            summary = "已手动停止"
            error_message = "run cancelled by user"
            break

        with _connect() as db:
            db.execute(
                """
                update test_runs
                set current_step_name = ?, progress_percent = ?, completed_steps = ?
                where id = ?
                """,
                (step["name"], _progress_percent(index - 1, len(steps)), index - 1, run["id"]),
            )
            db.commit()

        step_obj = SimpleNamespace(**step)
        step_started = _now()
        execution = await execute_step(profile=profile_obj, step=step_obj)
        step_finished = _now()
        result = execution.driver_result
        step_status = "passed" if result.success else execution.failure_kind or "error"
        _insert_step_result(run["id"], step, result, step_status, step_started, step_finished)
        _update_run_progress(run["id"], index, len(steps))
        if step_status != "passed":
            step_final_status = "failed" if step_status == "failed" else "error"
            if final_status != "error":
                final_status = step_final_status
            summary = "测试失败" if final_status == "failed" else "测试异常"
            error_message = f"{step['name']}: {result.message}"
            if not step.get("continue_on_failure", False):
                break
            summary = "测试失败，已按配置继续执行后续步骤"

    _finish_run(
        run["id"],
        status=final_status,
        result="pass" if final_status == "passed" else final_status,
        summary=summary,
        error_message=error_message,
    )


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    ensure_mvp_schema()
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def _recover_incomplete_runs() -> None:
    with _connect() as db:
        db.execute(
            """
            update test_runs
            set status = 'waiting',
                summary = '服务重启后重新排队',
                current_step_name = null
            where status in ('running', 'stopping', 'pending')
            """,
        )
        db.execute(
            """
            update test_runs
            set status = 'passed'
            where status = 'completed'
            """,
        )
        db.commit()


def _has_waiting_runs() -> bool:
    with _connect() as db:
        row = db.execute(
            """
            select 1 from test_runs
            where status = 'waiting'
            limit 1
            """,
        ).fetchone()
    return row is not None


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_ms(started_at: str, finished_at: str) -> int:
    start = datetime.fromisoformat(started_at)
    finish = datetime.fromisoformat(finished_at)
    return int((finish - start).total_seconds() * 1000)


def _case_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["enabled"] = bool(payload.get("enabled"))
    payload["config_json"] = _loads(payload.get("config_json"), {})
    return payload


def _step_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["case_id"] = payload.pop("case_id")
    payload["config_json"] = _loads(payload.get("config_json"), {})
    payload["expected_json"] = _loads(payload.get("expected_json"), {})
    payload["continue_on_failure"] = bool(payload.get("continue_on_failure"))
    return payload


def _run_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["profile_snapshot_json"] = _loads(payload.get("profile_snapshot_json"), None)
    payload["case_snapshot_json"] = _loads(payload.get("case_snapshot_json"), None)
    payload["cancel_requested"] = bool(payload.get("cancel_requested"))
    payload["total_steps"] = int(payload.get("total_steps") or 0)
    payload["completed_steps"] = int(payload.get("completed_steps") or 0)
    payload["progress_percent"] = int(payload.get("progress_percent") or 0)
    payload["status"] = _normalized_status(str(payload.get("status") or ""))
    return payload


def _step_result_from_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    payload["data_json"] = _loads(payload.get("data_json"), None)
    return payload


def _loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _to_db(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _finish_run(
    run_id: int,
    *,
    status: str,
    result: str,
    summary: str,
    error_message: str,
) -> None:
    started_at = get_run_detail(run_id)
    finished_at = _now()
    duration_ms = 0
    if started_at is not None and started_at.get("started_at"):
        duration_ms = _duration_ms(str(started_at["started_at"]), finished_at)

    with _connect() as db:
        db.execute(
            """
            update test_runs
            set status = ?, result = ?, summary = ?, error_message = ?,
                finished_at = ?, ended_at = ?, duration_ms = ?, current_step_name = ?,
                progress_percent = ?, completed_steps = ?
            where id = ?
            """,
            (
                status,
                result,
                summary,
                error_message,
                finished_at,
                finished_at,
                duration_ms,
                None,
                100 if status == "passed" else _current_progress_value(run_id),
                _current_completed_steps(run_id),
                run_id,
            ),
        )
        db.commit()


def _update_run_progress(run_id: int, completed_steps: int, total_steps: int) -> None:
    with _connect() as db:
        db.execute(
            """
            update test_runs
            set completed_steps = ?, progress_percent = ?
            where id = ?
            """,
            (completed_steps, _progress_percent(completed_steps, total_steps), run_id),
        )
        db.commit()


def _progress_percent(completed_steps: int, total_steps: int) -> int:
    if total_steps <= 0:
        return 0
    return min(100, int((completed_steps / total_steps) * 100))


def _current_progress_value(run_id: int) -> int:
    with _connect() as db:
        row = db.execute("select progress_percent from test_runs where id = ?", (run_id,)).fetchone()
    return int(row["progress_percent"]) if row and row["progress_percent"] is not None else 0


def _current_completed_steps(run_id: int) -> int:
    with _connect() as db:
        row = db.execute("select completed_steps from test_runs where id = ?", (run_id,)).fetchone()
    return int(row["completed_steps"]) if row and row["completed_steps"] is not None else 0


def _attach_queue_positions(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with _connect() as db:
        rows = db.execute(
            """
            select id from test_runs
            where status = 'waiting'
            order by created_at, id
            """,
        ).fetchall()
    positions = {int(row["id"]): index + 1 for index, row in enumerate(rows)}
    for run in runs:
        run["queue_position"] = positions.get(run["id"])
    return runs


def _normalized_status(status: str) -> str:
    if status == "completed":
        return "passed"
    if status == "pending":
        return "waiting"
    return status
