from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from backend.core.config import BASE_DIR
from backend.runner import mvp_sqlite
from backend.runner.step_schemas import validate_step_payload


class TestRunYamlImportError(ValueError):
    pass


def import_testrun_yaml_and_enqueue(yaml_path: Path) -> dict[str, Any]:
    payload = _load_yaml(yaml_path)
    name = _normalized_name(payload, yaml_path)
    description = str(payload.get("description") or "").strip() or None
    hardware = _mapping(payload.get("hardware"), "hardware")
    steps = payload.get("steps")
    if not isinstance(steps, list) or not steps:
        raise TestRunYamlImportError("steps must be a non-empty array")

    profile_payload = _build_profile_payload(name, description, hardware)
    profile = mvp_sqlite.save_profile(profile_payload)

    case_payload = {
        "name": name,
        "description": _case_description(description, yaml_path),
        "enabled": True,
    }
    case = mvp_sqlite.save_case(case_payload)

    imported_steps: list[dict[str, Any]] = []
    for index, raw_step in enumerate(steps):
        step_payload = _build_step_payload(raw_step, index)
        validate_step_payload(
            step_type=step_payload["step_type"],
            config_json=step_payload["config_json"],
            expected_json=step_payload["expected_json"],
            timeout_ms=step_payload["timeout_ms"],
        )
        imported_steps.append(mvp_sqlite.save_step(int(case["id"]), step_payload))

    return {
        "source_file": str(yaml_path.relative_to(BASE_DIR)),
        "profile": profile,
        "test_case": {**case, "steps": imported_steps},
        "run_name": f"{name} @ {datetime.now(timezone.utc).isoformat()}",
    }


def _load_yaml(yaml_path: Path) -> dict[str, Any]:
    if not yaml_path.exists() or not yaml_path.is_file():
        raise TestRunYamlImportError("uploaded yaml file not found")

    try:
        loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TestRunYamlImportError(f"invalid yaml: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise TestRunYamlImportError("yaml file must be utf-8 text") from exc

    if not isinstance(loaded, dict):
        raise TestRunYamlImportError("yaml root must be an object")
    return loaded


def _normalized_name(payload: dict[str, Any], yaml_path: Path) -> str:
    value = str(payload.get("name") or "").strip()
    return value or yaml_path.stem


def _build_profile_payload(
    name: str,
    description: str | None,
    hardware: dict[str, Any],
) -> dict[str, Any]:
    bit = _optional_mapping(hardware.get("bit"))
    elf = _optional_mapping(hardware.get("elf"))
    jlink = _optional_mapping(hardware.get("jlink"))
    uart = _optional_mapping(hardware.get("uart"))
    scope = _optional_mapping(hardware.get("scope"))

    timeout_s = uart.get("timeout_s")
    timeout_ms = None if timeout_s in (None, "") else int(float(timeout_s) * 1000)

    return {
        "name": f"{name} Hardware",
        "description": description,
        "is_default": False,
        "board_name": hardware.get("board"),
        "board_serial": hardware.get("board_serial"),
        "bit_file": bit.get("file"),
        "bit_program_channel": bit.get("channel"),
        "elf_file": elf.get("file"),
        "jlink_serial": jlink.get("serial"),
        "jlink_interface": jlink.get("interface"),
        "jlink_device": jlink.get("device"),
        "jlink_speed_khz": _optional_int(jlink.get("speed_khz")),
        "uart_port": uart.get("port"),
        "uart_baudrate": _optional_int(uart.get("baudrate")) or 115200,
        "uart_bytesize": _optional_int(uart.get("bytesize")) or 8,
        "uart_parity": uart.get("parity") or "N",
        "uart_stopbits": _optional_float(uart.get("stopbits")) or 1.0,
        "uart_timeout_ms": timeout_ms or 1000,
        "scope_model": scope.get("model"),
        "scope_ip": scope.get("ip"),
        "scope_port": _optional_int(scope.get("port")),
        "scope_channel": scope.get("channel"),
    }


def _case_description(description: str | None, yaml_path: Path) -> str:
    suffix = f"Imported from {yaml_path.name}"
    if description:
        return f"{description}\n\n{suffix}"
    return suffix


def _build_step_payload(raw_step: Any, index: int) -> dict[str, Any]:
    step = _mapping(raw_step, f"steps[{index}]")
    step_type = str(step.get("type") or "").strip()
    if not step_type:
        raise TestRunYamlImportError(f"steps[{index}].type is required")

    params = _optional_mapping(step.get("params"))
    expected = _optional_mapping(step.get("expected"))
    timeout_ms = _optional_int(step.get("timeout_ms")) or 30000
    step_name = str(step.get("name") or step_type).strip() or step_type
    continue_on_failure = _optional_bool(
        step.get(
            "continue_on_failure",
            step.get("continue_on_fail", step.get("continue_after_failure", False)),
        )
    )

    normalized_type, config_json, expected_json = _normalize_step(step_type, params, expected)
    return {
        "order_index": index,
        "step_type": normalized_type,
        "name": step_name,
        "config_json": config_json,
        "expected_json": expected_json,
        "timeout_ms": timeout_ms,
        "continue_on_failure": continue_on_failure,
    }


def _normalize_step(
    step_type: str,
    params: dict[str, Any],
    expected: dict[str, Any],
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if step_type == "program_bit":
        return step_type, _copy_present(params), _copy_present(expected)

    if step_type == "program_elf":
        return step_type, _copy_present(params), _copy_present(expected)

    if step_type == "uart_wait":
        contains = params.get("expect_contains")
        if contains in (None, ""):
            raise TestRunYamlImportError("uart_wait requires params.expect_contains")
        return (
            "uart_wait",
            _copy_present(
                {
                    "contains": contains,
                    "encoding": params.get("encoding"),
                    "read_timeout_ms": params.get("read_timeout_ms"),
                }
            ),
            {},
        )

    if step_type == "uart_query":
        command = params.get("command", params.get("send"))
        if command in (None, ""):
            raise TestRunYamlImportError("uart_query requires params.send or params.command")
        expected_contains = params.get("expect_contains", expected.get("contains"))
        return (
            "uart_query",
            _copy_present(
                {
                    "command": command,
                    "encoding": params.get("encoding"),
                    "read_timeout_ms": params.get("read_timeout_ms"),
                    "append_newline": params.get("append_newline", False),
                }
            ),
            _copy_present({"contains": expected_contains, **expected}),
        )

    if step_type == "scope_measure":
        measure = params.get("measure", params.get("measurement"))
        if measure in (None, ""):
            raise TestRunYamlImportError("scope_measure requires params.measurement or params.measure")
        return (
            "scope_measure",
            _copy_present(
                {
                    "channel": params.get("channel"),
                    "measure": measure,
                    "resource": params.get("resource"),
                }
            ),
            _copy_present(expected),
        )

    if step_type == "sleep":
        return step_type, _copy_present(params), _copy_present(expected)

    if step_type in {"assert_value", "assert_text"}:
        return step_type, _copy_present(params), _copy_present(expected)

    raise TestRunYamlImportError(f"unsupported yaml step type: {step_type}")


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TestRunYamlImportError(f"{label} must be an object")
    return value


def _optional_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _copy_present(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}
