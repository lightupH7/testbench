from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from backend.api.schemas import ManualExecuteRequest
from backend.drivers.base import DriverResult
from backend.drivers.jlink_driver import JLinkDriver
from backend.drivers.vivado_driver import VivadoDriver


OutputCallback = Callable[[str, str, str], None]


def execute_manual_action(
    request: ManualExecuteRequest,
    output_callback: OutputCallback | None = None,
) -> DriverResult:
    if request.action == "program_bit":
        validation = _validate_file(request.bit_file, ".bit", "bit_file")
        if validation is not None:
            return validation
        return _program_bit(request, output_callback)

    if request.action == "program_elf":
        validation = _validate_file(request.elf_file, ".elf", "elf_file")
        if validation is not None:
            return validation
        return _program_elf(request, output_callback)

    bit_validation = _validate_file(request.bit_file, ".bit", "bit_file")
    if bit_validation is not None:
        return bit_validation

    elf_validation = _validate_file(request.elf_file, ".elf", "elf_file")
    if elf_validation is not None:
        return elf_validation

    bit_result = _program_bit(request, output_callback)
    if not bit_result.success:
        return DriverResult.fail(
            message="bit programming failed; elf programming skipped",
            data={"bit_result": _serialize_driver_result(bit_result), "elf_result": None},
            stdout="",
            stderr="",
            returncode=bit_result.returncode or 1,
        )

    elf_result = _program_elf(request, output_callback)
    success = elf_result.success
    return DriverResult(
        success=success,
        message=(
            "bit and elf programmed successfully"
            if success
            else "bit programmed successfully; elf programming failed"
        ),
        data={
            "bit_result": _serialize_driver_result(bit_result),
            "elf_result": _serialize_driver_result(elf_result),
        },
        stdout="",
        stderr="",
        returncode=0 if success else (elf_result.returncode or 1),
    )


def _program_bit(
    request: ManualExecuteRequest,
    output_callback: OutputCallback | None = None,
) -> DriverResult:
    driver = VivadoDriver()
    try:
        return driver.program_bit(
            bit_path=request.bit_file or "",
            vivado_bin=request.vivado_path,
            hw_server_url=request.hw_server_url,
            timeout=request.timeout,
            on_output=_driver_output_callback("program_bit", output_callback),
        )
    finally:
        driver.close()


def _program_elf(
    request: ManualExecuteRequest,
    output_callback: OutputCallback | None = None,
) -> DriverResult:
    driver = JLinkDriver()
    try:
        return driver.program_elf(
            elf_path=request.elf_file or "",
            device=request.device,
            interface=request.interface,
            speed=request.speed,
            timeout=request.timeout,
            on_output=_driver_output_callback("program_elf", output_callback),
        )
    finally:
        driver.close()


def _validate_file(path_value: str | None, expected_suffix: str, field_name: str) -> DriverResult | None:
    if not path_value:
        return DriverResult.fail(
            message=f"{field_name} is required",
            data={"field": field_name},
            returncode=1,
        )

    path = Path(path_value).expanduser()
    if path.suffix.lower() != expected_suffix:
        return DriverResult.fail(
            message=f"{field_name} must be a {expected_suffix} file",
            data={"field": field_name, "path": path_value},
            returncode=1,
        )

    resolved = path.resolve()
    if not resolved.exists():
        return DriverResult.fail(
            message=f"{field_name} not found",
            data={"field": field_name, "path": str(resolved)},
            returncode=1,
        )

    if not resolved.is_file():
        return DriverResult.fail(
            message=f"{field_name} is not a file",
            data={"field": field_name, "path": str(resolved)},
            returncode=1,
        )

    return None


def _serialize_driver_result(result: DriverResult) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def _driver_output_callback(
    label: str,
    callback: OutputCallback | None,
) -> Callable[[str, str], None] | None:
    if callback is None:
        return None

    def emit(channel: str, chunk: str) -> None:
        callback(label, channel, chunk)

    return emit
