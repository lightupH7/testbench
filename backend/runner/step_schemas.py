from __future__ import annotations

from typing import Any


STEP_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "program_bit": {
        "required_config": [],
        "required_expected": [],
    },
    "program_elf": {
        "required_config": [],
        "required_expected": [],
    },
    "uart_query": {
        "required_config": ["command"],
        "required_expected": [],
    },
    "uart_wait": {
        "required_config": ["contains"],
        "required_expected": [],
    },
    "sleep": {
        "required_config": ["seconds"],
        "required_expected": [],
    },
    "scope_measure": {
        "required_config": ["channel", "measure"],
        "required_expected": [],
    },
    "assert_value": {
        "required_config": ["value"],
        "required_expected": [],
    },
    "assert_text": {
        "required_config": ["text"],
        "required_expected": [],
    },
}


class StepSchemaError(ValueError):
    pass


def validate_step_payload(
    *,
    step_type: str,
    config_json: Any,
    expected_json: Any,
    timeout_ms: int,
) -> None:
    schema = STEP_SCHEMAS.get(step_type)
    if schema is None:
        raise StepSchemaError(f"unsupported step_type: {step_type}")

    if not isinstance(config_json, dict):
        raise StepSchemaError("config_json must be an object")

    if not isinstance(expected_json, dict):
        raise StepSchemaError("expected_json must be an object")

    if timeout_ms <= 0:
        raise StepSchemaError("timeout_ms must be greater than 0")

    missing_config = _missing_keys(config_json, schema["required_config"])
    if missing_config:
        raise StepSchemaError(f"missing config_json keys: {', '.join(missing_config)}")

    missing_expected = _missing_keys(expected_json, schema["required_expected"])
    if missing_expected:
        raise StepSchemaError(f"missing expected_json keys: {', '.join(missing_expected)}")


def _missing_keys(payload: dict[str, Any], keys: list[str]) -> list[str]:
    return [key for key in keys if key not in payload or payload[key] in (None, "")]
