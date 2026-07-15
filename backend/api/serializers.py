from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.models import (
    HardwareProfile,
    TestCase,
    TestCaseResult,
    TestLog,
    TestPlan,
    TestRun,
    TestStep,
    TestStepResult,
)
from backend.drivers.base import DriverResult


def serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def serialize_driver_result(result: DriverResult) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def serialize_hardware_profile(profile: HardwareProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "is_default": profile.is_default,
        "board_name": profile.board_name,
        "board_serial": profile.board_serial,
        "bit_file": profile.bit_file,
        "bit_program_channel": profile.bit_program_channel,
        "elf_file": profile.elf_file,
        "jlink_serial": profile.jlink_serial,
        "jlink_interface": profile.jlink_interface,
        "jlink_device": profile.jlink_device,
        "jlink_speed_khz": profile.jlink_speed_khz,
        "uart_port": profile.uart_port,
        "uart_baudrate": profile.uart_baudrate,
        "uart_bytesize": profile.uart_bytesize,
        "uart_parity": profile.uart_parity,
        "uart_stopbits": profile.uart_stopbits,
        "uart_timeout_ms": profile.uart_timeout_ms,
        "scope_model": profile.scope_model,
        "scope_ip": profile.scope_ip,
        "scope_port": profile.scope_port,
        "scope_channel": profile.scope_channel,
        "created_at": serialize_datetime(profile.created_at),
        "updated_at": serialize_datetime(profile.updated_at),
    }


def serialize_test_case(case: TestCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "name": case.name,
        "type": case.type,
        "description": case.description,
        "config_json": case.config_json,
        "enabled": case.enabled,
        "created_at": serialize_datetime(case.created_at),
        "updated_at": serialize_datetime(case.updated_at),
    }


def serialize_test_step(step: TestStep) -> dict[str, Any]:
    return {
        "id": step.id,
        "case_id": step.case_id,
        "order_index": step.order_index,
        "step_type": step.step_type,
        "name": step.name,
        "config_json": step.config_json,
        "expected_json": step.expected_json,
        "timeout_ms": step.timeout_ms,
        "continue_on_failure": step.continue_on_failure,
        "created_at": serialize_datetime(step.created_at),
        "updated_at": serialize_datetime(step.updated_at),
    }


def serialize_test_plan(plan: TestPlan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "name": plan.name,
        "board": plan.board,
        "description": plan.description,
        "setup_json": plan.setup_json,
        "enabled": plan.enabled,
        "created_at": serialize_datetime(plan.created_at),
        "updated_at": serialize_datetime(plan.updated_at),
    }


def serialize_test_run(run: TestRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "plan_id": run.plan_id,
        "hardware_profile_id": run.hardware_profile_id,
        "test_case_id": run.test_case_id,
        "name": run.name,
        "status": run.status,
        "result": run.result,
        "summary": run.summary,
        "error_message": run.error_message,
        "selected_case_ids_json": run.selected_case_ids_json,
        "profile_snapshot_json": run.profile_snapshot_json,
        "case_snapshot_json": run.case_snapshot_json,
        "started_at": serialize_datetime(run.started_at),
        "finished_at": serialize_datetime(run.finished_at),
        "duration_ms": run.duration_ms,
        "ended_at": serialize_datetime(run.ended_at),
        "created_at": serialize_datetime(run.created_at),
    }


def serialize_test_case_result(result: TestCaseResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "run_id": result.run_id,
        "case_id": result.case_id,
        "case_name": result.case_name,
        "case_type": result.case_type,
        "status": result.status,
        "result": result.result,
        "log": result.log,
        "started_at": serialize_datetime(result.started_at),
        "ended_at": serialize_datetime(result.ended_at),
        "created_at": serialize_datetime(result.created_at),
    }


def serialize_test_step_result(result: TestStepResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "run_id": result.run_id,
        "test_step_id": result.test_step_id,
        "order_index": result.order_index,
        "step_name": result.step_name,
        "step_type": result.step_type,
        "name": result.name,
        "type": result.type,
        "status": result.status,
        "result": result.result,
        "message": result.message,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "data_json": result.data_json,
        "log": result.log,
        "started_at": serialize_datetime(result.started_at),
        "finished_at": serialize_datetime(result.finished_at),
        "duration_ms": result.duration_ms,
        "ended_at": serialize_datetime(result.ended_at),
        "created_at": serialize_datetime(result.created_at),
    }


def serialize_test_log(log: TestLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "run_id": log.run_id,
        "case_result_id": log.case_result_id,
        "level": log.level,
        "source": log.source,
        "message": log.message,
        "created_at": serialize_datetime(log.created_at),
    }


def serialize_serial_port(port: Any) -> dict[str, Any]:
    return {
        "device": port.device,
        "name": port.name,
        "description": port.description,
        "hwid": port.hwid,
        "vid": port.vid,
        "pid": port.pid,
        "serial_number": port.serial_number,
        "manufacturer": port.manufacturer,
        "product": port.product,
        "interface": port.interface,
    }
