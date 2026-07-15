from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from backend.api.schemas import ProgramBitRequest, ProgramElfRequest
from backend.db.models import HardwareProfile, TestStep
from backend.drivers.base import DriverResult
from backend.drivers.scope_driver import ScopeDriver
from backend.drivers.uart_driver import UartDriver
from backend.runner.step_schemas import StepSchemaError, validate_step_payload
from backend.services.programming import program_bit, program_elf


@dataclass
class StepExecutionResult:
    driver_result: DriverResult
    failure_kind: str | None = None


async def execute_step(
    *,
    profile: HardwareProfile,
    step: TestStep,
) -> StepExecutionResult:
    try:
        validate_step_payload(
            step_type=step.step_type,
            config_json=step.config_json,
            expected_json=step.expected_json,
            timeout_ms=step.timeout_ms,
        )
        result = await asyncio.wait_for(
            _execute_step_body(profile=profile, step=step),
            timeout=step.timeout_ms / 1000,
        )
        return result
    except StepSchemaError as exc:
        return StepExecutionResult(
            driver_result=DriverResult.fail(message=str(exc), stderr=str(exc)),
            failure_kind="error",
        )
    except TimeoutError as exc:
        return StepExecutionResult(
            driver_result=DriverResult.fail(message="step timeout", stderr=str(exc)),
            failure_kind="error",
        )
    except Exception as exc:  # noqa: BLE001
        return StepExecutionResult(
            driver_result=DriverResult.fail(message="step execution crashed", stderr=str(exc)),
            failure_kind="error",
        )


async def _execute_step_body(
    *,
    profile: HardwareProfile,
    step: TestStep,
) -> StepExecutionResult:
    if step.step_type == "program_bit":
        return await _program_bit(profile, step)
    if step.step_type == "program_elf":
        return await _program_elf(profile, step)
    if step.step_type == "uart_query":
        return await _uart_query(profile, step)
    if step.step_type == "uart_wait":
        return await _uart_wait(profile, step)
    if step.step_type == "sleep":
        return await _sleep(step)
    if step.step_type == "scope_measure":
        return await _scope_measure(profile, step)
    if step.step_type == "assert_value":
        return _assert_value(step)
    if step.step_type == "assert_text":
        return _assert_text(step)

    return StepExecutionResult(
        driver_result=DriverResult.fail(message=f"unsupported step_type: {step.step_type}"),
        failure_kind="error",
    )


async def _program_bit(profile: HardwareProfile, step: TestStep) -> StepExecutionResult:
    bit_path = step.config_json.get("bit_file") or profile.bit_file
    if not bit_path:
        return _error("bit_file is required")

    request = ProgramBitRequest(
        bit_path=str(bit_path),
        hw_target=profile.bit_program_channel,
        device=step.config_json.get("device"),
        vivado_bin=step.config_json.get("vivado_bin"),
        python_bin=step.config_json.get("python_bin"),
        keep_tcl=bool(step.config_json.get("keep_tcl", False)),
    )
    result = await asyncio.to_thread(program_bit, request)
    return StepExecutionResult(result, None if result.success else "error")


async def _program_elf(profile: HardwareProfile, step: TestStep) -> StepExecutionResult:
    elf_path = step.config_json.get("elf_file") or profile.elf_file
    if not elf_path:
        return _error("elf_file is required")

    request = ProgramElfRequest(
        elf_path=str(elf_path),
        jtag_speed=int(profile.jlink_speed_khz or step.config_json.get("jtag_speed") or 4000),
        jlink_device=profile.jlink_device,
        interface=profile.jlink_interface,
    )
    result = await asyncio.to_thread(program_elf, request)
    return StepExecutionResult(result, None if result.success else "error")


async def _uart_query(profile: HardwareProfile, step: TestStep) -> StepExecutionResult:
    if not profile.uart_port:
        return _error("hardware profile uart_port is required")

    config = step.config_json
    expected = step.expected_json
    encoding = str(config.get("encoding") or "utf-8")
    command = str(config["command"])
    read_timeout = int(config.get("read_timeout_ms") or profile.uart_timeout_ms or 3000) / 1000
    contains = expected.get("contains")

    driver = UartDriver(
        config={
            "port": profile.uart_port,
            "baudrate": profile.uart_baudrate,
            "bytesize": profile.uart_bytesize,
            "parity": profile.uart_parity,
            "stopbits": profile.uart_stopbits,
            "timeout": 0.05,
            "write_timeout": 1.0,
        },
    )

    try:
        connect_result = await asyncio.to_thread(driver.connect)
        if not connect_result.success:
            return StepExecutionResult(connect_result, "error")

        await asyncio.to_thread(driver.reset_input_buffer)
        write_result = await asyncio.to_thread(
            driver.write,
            command,
            encoding,
            bool(config.get("append_newline", True)),
        )
        if not write_result.success:
            return StepExecutionResult(write_result, "error")

        if contains is not None:
            read_result = await asyncio.to_thread(
                driver.read_until,
                str(contains),
                read_timeout,
                encoding,
                "replace",
            )
            return StepExecutionResult(read_result, None if read_result.success else "failed")

        started = time.monotonic()
        chunks: list[str] = []
        while time.monotonic() - started < read_timeout:
            result = await asyncio.to_thread(driver.read_available, 4096, True, encoding, "replace")
            if result.stdout:
                chunks.append(result.stdout)
            await asyncio.sleep(0.05)

        stdout = "".join(chunks)
        return StepExecutionResult(
            DriverResult.ok("uart query completed", stdout=stdout, data={"stdout": stdout}),
        )
    finally:
        await asyncio.to_thread(driver.close)


async def _uart_wait(profile: HardwareProfile, step: TestStep) -> StepExecutionResult:
    if not profile.uart_port:
        return _error("hardware profile uart_port is required")

    config = step.config_json
    contains = config.get("contains")
    if contains in (None, ""):
        return _error("uart_wait contains is required")

    encoding = str(config.get("encoding") or "utf-8")
    read_timeout = int(config.get("read_timeout_ms") or profile.uart_timeout_ms or 3000) / 1000

    driver = UartDriver(
        config={
            "port": profile.uart_port,
            "baudrate": profile.uart_baudrate,
            "bytesize": profile.uart_bytesize,
            "parity": profile.uart_parity,
            "stopbits": profile.uart_stopbits,
            "timeout": 0.05,
            "write_timeout": 1.0,
        },
    )

    try:
        connect_result = await asyncio.to_thread(driver.connect)
        if not connect_result.success:
            return StepExecutionResult(connect_result, "error")

        read_result = await asyncio.to_thread(
            driver.read_until,
            str(contains),
            read_timeout,
            encoding,
            "replace",
        )
        return StepExecutionResult(read_result, None if read_result.success else "failed")
    finally:
        await asyncio.to_thread(driver.close)


async def _sleep(step: TestStep) -> StepExecutionResult:
    seconds = float(step.config_json["seconds"])
    if seconds < 0:
        return _error("sleep seconds must be greater than or equal to 0")
    await asyncio.sleep(seconds)
    return StepExecutionResult(DriverResult.ok("sleep completed", data={"seconds": seconds}))


async def _scope_measure(profile: HardwareProfile, step: TestStep) -> StepExecutionResult:
    resource = step.config_json.get("resource") or _scope_resource(profile)
    if not resource:
        return _error("scope resource is required")

    channel = str(step.config_json["channel"] or profile.scope_channel or "CH1")
    measure = str(step.config_json["measure"]).upper()
    expected = step.expected_json
    driver = ScopeDriver(config={"resource": resource, "timeout_ms": profile.uart_timeout_ms})

    try:
        connect_result = await asyncio.to_thread(driver.connect)
        if not connect_result.success:
            return StepExecutionResult(connect_result, "error")

        result = await asyncio.to_thread(driver.read_measurement, channel, measure)
        if not result.success:
            return StepExecutionResult(result, "error")

        value = float(result.data["value"])
        if not _value_in_expected_range(value, expected):
            result.success = False
            result.message = "scope measurement out of expected range"
            return StepExecutionResult(result, "failed")

        result.message = "scope measurement passed"
        return StepExecutionResult(result)
    finally:
        await asyncio.to_thread(driver.close)


def _assert_value(step: TestStep) -> StepExecutionResult:
    value = step.config_json["value"]
    expected = step.expected_json
    if not _value_in_expected_range(float(value), expected):
        return StepExecutionResult(
            DriverResult.fail("assert_value failed", data={"value": value, "expected": expected}),
            "failed",
        )
    return StepExecutionResult(DriverResult.ok("assert_value passed", data={"value": value}))


def _assert_text(step: TestStep) -> StepExecutionResult:
    text = str(step.config_json["text"])
    contains = step.expected_json.get("contains")
    equals = step.expected_json.get("equals")
    ok = True
    if contains is not None:
        ok = str(contains) in text
    if equals is not None:
        ok = text == str(equals)
    if not ok:
        return StepExecutionResult(
            DriverResult.fail("assert_text failed", data={"text": text, "expected": step.expected_json}),
            "failed",
        )
    return StepExecutionResult(DriverResult.ok("assert_text passed", data={"text": text}))


def _error(message: str) -> StepExecutionResult:
    return StepExecutionResult(
        driver_result=DriverResult.fail(message=message, stderr=message),
        failure_kind="error",
    )


def _scope_resource(profile: HardwareProfile) -> str | None:
    if not profile.scope_ip:
        return None
    if profile.scope_port:
        return f"TCPIP::{profile.scope_ip}::{profile.scope_port}::SOCKET"
    return f"TCPIP::{profile.scope_ip}::INSTR"


def _value_in_expected_range(value: float, expected: dict[str, Any]) -> bool:
    min_value = expected.get("min")
    max_value = expected.get("max")
    if min_value is not None and value < float(min_value):
        return False
    if max_value is not None and value > float(max_value):
        return False
    equals = expected.get("equals")
    if equals is not None and value != float(equals):
        return False
    return True
