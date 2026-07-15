from __future__ import annotations

import asyncio
import contextlib
import os
import pty
import subprocess
from pathlib import Path
from typing import Any

from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from serial.tools import list_ports

from backend.api.schemas import (
    CreateTestRunRequest,
    HardwareProfilePayload,
    ImportUploadedTestRunRequest,
    JLinkControlRequest,
    ManualExecuteRequest,
    ProgramBitRequest,
    ProgramElfRequest,
    ScopeChannelRequest,
    ScopeConnectionRequest,
    ScopeControlRequest,
    ScopeMeasureRequest,
    ScopeWaveformRequest,
    TestCasePayload,
    TestStepPayload,
)
from backend.api.serializers import serialize_driver_result, serialize_serial_port
from backend.core.config import BASE_DIR
from backend.db.config import DB_PATH
from backend.drivers.base import DriverResult
from backend.drivers.jlink_driver import JLinkDriver
from backend.drivers.scope_driver import ScopeDriver
from backend.runner import mvp_sqlite
from backend.runner.step_schemas import StepSchemaError, validate_step_payload
from backend.services.programming import program_bit as run_program_bit
from backend.services.programming import program_elf as run_program_elf
from backend.services.manual import execute_manual_action
from backend.services.terminal_monitor import terminal_broadcast_hub
from backend.services.uart_monitor import UartMonitorSession
from backend.runner.automation import (
    create_run_sync,
    get_run_sync,
    list_case_results_sync,
    list_logs_sync,
    list_runs_sync,
    list_step_results_sync,
    run_test_run,
)
from backend.runner.yaml_importer import TestRunYamlImportError, import_testrun_yaml_and_enqueue

router = APIRouter(prefix="/api")

UPLOAD_TARGETS = {
    "bit": {
        "directory": BASE_DIR / "artifacts" / "bitstreams",
        "suffixes": {".bit"},
    },
    "elf": {
        "directory": BASE_DIR / "artifacts" / "firmware",
        "suffixes": {".elf"},
    },
    "testrun": {
        "directory": BASE_DIR / "artifacts" / "testruns",
        "suffixes": {".yaml", ".yml"},
    },
}


@router.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "database": {
            "engine": "sqlite",
            "path": str(DB_PATH),
        },
    }


@router.get("/summary")
async def summary() -> dict[str, int]:
    return {
        "hardware_profiles": mvp_sqlite.count_table("hardware_profiles"),
        "test_cases": mvp_sqlite.count_table("test_cases"),
        "test_plans": mvp_sqlite.count_table("test_plans"),
        "test_runs": mvp_sqlite.count_table("test_runs"),
    }


@router.get("/hardware-profiles")
async def list_hardware_profiles() -> list[dict[str, Any]]:
    return mvp_sqlite.list_profiles()


@router.get("/hardware-profiles/{profile_id}")
async def get_hardware_profile(profile_id: int) -> dict[str, Any]:
    profile = mvp_sqlite.get_profile(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="hardware profile not found")
    return profile


@router.post("/hardware-profiles")
async def create_hardware_profile(payload: HardwareProfilePayload) -> dict[str, Any]:
    return mvp_sqlite.save_profile(payload.model_dump())


@router.put("/hardware-profiles/{profile_id}")
async def update_hardware_profile(
    profile_id: int,
    payload: HardwareProfilePayload,
) -> dict[str, Any]:
    if mvp_sqlite.get_profile(profile_id) is None:
        raise HTTPException(status_code=404, detail="hardware profile not found")
    return mvp_sqlite.save_profile(payload.model_dump(), profile_id)


@router.delete("/hardware-profiles/{profile_id}")
async def delete_hardware_profile(profile_id: int) -> dict[str, Any]:
    if not mvp_sqlite.delete_profile(profile_id):
        raise HTTPException(status_code=404, detail="hardware profile not found")
    return {"ok": True}


@router.get("/test-cases")
async def list_test_cases() -> list[dict[str, Any]]:
    return mvp_sqlite.list_cases()


@router.get("/test-cases/{case_id}")
async def get_test_case(case_id: int) -> dict[str, Any]:
    case = mvp_sqlite.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="test case not found")
    return {**case, "steps": mvp_sqlite.list_steps(case_id)}


@router.post("/test-cases")
async def create_test_case(payload: TestCasePayload) -> dict[str, Any]:
    return mvp_sqlite.save_case(payload.model_dump())


@router.put("/test-cases/{case_id}")
async def update_test_case(case_id: int, payload: TestCasePayload) -> dict[str, Any]:
    if mvp_sqlite.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="test case not found")
    return mvp_sqlite.save_case(payload.model_dump(), case_id)


@router.delete("/test-cases/{case_id}")
async def delete_test_case(case_id: int) -> dict[str, Any]:
    if not mvp_sqlite.delete_case(case_id):
        raise HTTPException(status_code=404, detail="test case not found")
    return {"ok": True}


@router.get("/test-cases/{case_id}/steps")
async def list_test_steps(case_id: int) -> list[dict[str, Any]]:
    if mvp_sqlite.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="test case not found")
    return mvp_sqlite.list_steps(case_id)


@router.post("/test-cases/{case_id}/steps")
async def create_test_step(case_id: int, payload: TestStepPayload) -> dict[str, Any]:
    if mvp_sqlite.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="test case not found")
    _validate_step_payload_or_400(payload)
    return mvp_sqlite.save_step(case_id, payload.model_dump())


@router.put("/test-steps/{step_id}")
async def update_test_step(step_id: int, payload: TestStepPayload) -> dict[str, Any]:
    _validate_step_payload_or_400(payload)
    try:
        return mvp_sqlite.save_step(0, payload.model_dump(), step_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="test step not found") from exc


@router.delete("/test-steps/{step_id}")
async def delete_test_step(step_id: int) -> dict[str, Any]:
    if not mvp_sqlite.delete_step(step_id):
        raise HTTPException(status_code=404, detail="test step not found")
    return {"ok": True}


@router.get("/test-plans")
async def list_test_plans() -> list[dict[str, Any]]:
    return mvp_sqlite.list_test_plans()


@router.get("/test-runs")
async def list_test_runs() -> list[dict[str, Any]]:
    return mvp_sqlite.list_runs()


@router.post("/test-runs")
async def create_test_run(
    request: CreateTestRunRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    if request.hardware_profile_id is not None and request.test_case_id is not None:
        try:
            return await mvp_sqlite.enqueue_run(
                profile_id=request.hardware_profile_id,
                case_id=request.test_case_id,
                name=request.name,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not request.selected_case_ids:
        raise HTTPException(status_code=400, detail="selected_case_ids is required")

    try:
        run = create_run_sync(
            name=request.name,
            plan_id=request.plan_id,
            hardware_profile_id=request.hardware_profile_id,
            selected_case_ids=request.selected_case_ids,
            config_overrides=request.config_overrides or {},
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"message": "selected case not found or disabled", "data": str(exc)},
        ) from exc

    background_tasks.add_task(run_test_run, run["id"])
    return run


@router.post("/test-runs/{run_id}/stop")
async def stop_test_run(run_id: int) -> dict[str, Any]:
    try:
        return await mvp_sqlite.stop_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/test-runs/{run_id}")
async def get_test_run(run_id: int) -> dict[str, Any]:
    run = mvp_sqlite.get_run_detail(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="test run not found")
    return run


@router.get("/test-runs/{run_id}/case-results")
async def list_test_run_case_results(run_id: int) -> list[dict[str, Any]]:
    return list_case_results_sync(run_id)


@router.get("/test-runs/{run_id}/step-results")
async def list_test_run_step_results(run_id: int) -> list[dict[str, Any]]:
    return list_step_results_sync(run_id)


@router.get("/test-runs/{run_id}/logs")
async def list_test_run_logs(run_id: int) -> list[dict[str, Any]]:
    return list_logs_sync(run_id)


@router.get("/serial-ports")
async def list_serial_ports() -> dict[str, Any]:
    ports = list(list_ports.comports())
    return {
        "count": len(ports),
        "items": [serialize_serial_port(port) for port in ports],
    }


@router.get("/uploads")
async def list_uploaded_files() -> dict[str, list[dict[str, Any]]]:
    return {
        file_type: _list_upload_target_files(file_type)
        for file_type in UPLOAD_TARGETS
    }


@router.post("/uploads/{file_type}")
async def upload_file(file_type: str, request: Request) -> dict[str, Any]:
    target = UPLOAD_TARGETS.get(file_type)
    if target is None:
        raise HTTPException(status_code=404, detail="unsupported upload file type")

    filename = _upload_filename(request)

    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="uploaded file is empty")

    directory = target["directory"]
    directory.mkdir(parents=True, exist_ok=True)
    destination = _safe_upload_path(directory, filename)
    destination.write_bytes(payload)

    return {
        "type": file_type,
        "filename": destination.name,
        "path": str(destination.relative_to(BASE_DIR)),
        "size": destination.stat().st_size,
    }


@router.delete("/uploads/{file_type}/{filename}")
async def delete_uploaded_file(file_type: str, filename: str) -> dict[str, Any]:
    target = UPLOAD_TARGETS.get(file_type)
    if target is None:
        raise HTTPException(status_code=404, detail="unsupported upload file type")

    file_path = _safe_upload_path(target["directory"], Path(filename).name)
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="uploaded file not found")

    file_path.unlink()
    return {"ok": True, "filename": file_path.name, "type": file_type}


@router.post("/uploads/testrun/import")
async def import_uploaded_testrun(request: ImportUploadedTestRunRequest) -> dict[str, Any]:
    target = UPLOAD_TARGETS["testrun"]
    yaml_path = _safe_upload_path(target["directory"], Path(request.filename).name)
    try:
        imported = await asyncio.to_thread(import_testrun_yaml_and_enqueue, yaml_path)
    except TestRunYamlImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    run = await mvp_sqlite.enqueue_run(
        profile_id=int(imported["profile"]["id"]),
        case_id=int(imported["test_case"]["id"]),
        name=str(imported["run_name"]),
    )
    return {**imported, "run": run}


@router.post("/program/elf")
async def program_elf(request: ProgramElfRequest) -> dict[str, Any]:
    result = await asyncio.to_thread(run_program_elf, request)
    await terminal_broadcast_hub.broadcast(_format_driver_result("program_elf", result))
    return serialize_driver_result(result)


@router.post("/program/bit")
async def program_bit(request: ProgramBitRequest) -> dict[str, Any]:
    result = await asyncio.to_thread(run_program_bit, request)
    await terminal_broadcast_hub.broadcast(_format_driver_result("program_bit", result))
    return serialize_driver_result(result)


@router.post("/jlink/control")
async def control_jlink(request: JLinkControlRequest) -> dict[str, Any]:
    driver = JLinkDriver()
    try:
        result = await asyncio.to_thread(
            driver.control_target,
            request.action,
            jlink_lib=request.jlink_lib,
            jlink_serial=request.jlink_serial,
            jlink_device=request.jlink_device,
            interface=request.interface,
            speed=request.speed,
            timeout=request.timeout,
        )
    finally:
        driver.close()
    await terminal_broadcast_hub.broadcast(_format_driver_result("jlink_control", result))
    return serialize_driver_result(result)


@router.post("/scope/control")
async def control_scope(request: ScopeControlRequest) -> dict[str, Any]:
    config = {
        "resource": request.resource or _scope_resource_from_request(request),
        "visa_backend": request.visa_backend or "@py",
        "timeout_ms": request.timeout_ms,
    }
    driver = ScopeDriver(config=config)
    try:
        connect_result = await asyncio.to_thread(driver.connect_if_needed)
        if not connect_result.success:
            result = connect_result
        elif request.action == "check_connection":
            result = await asyncio.to_thread(driver.check_connection)
        elif request.action == "read_voltage":
            result = await asyncio.to_thread(
                driver.read_voltage,
                request.channel,
                request.measurement,
            )
        elif request.action == "read_waveform":
            result = await asyncio.to_thread(
                driver.read_waveform,
                request.channel,
                binary=request.binary,
                waveform_format=request.waveform_format,
                datatype=request.datatype,
            )
        else:
            result = await asyncio.to_thread(driver.read_frequency, request.channel)
    finally:
        driver.close()

    await terminal_broadcast_hub.broadcast(_format_driver_result("scope_control", result))
    return serialize_driver_result(result)


@router.post("/scope/idn")
async def scope_idn(request: ScopeConnectionRequest) -> dict[str, Any]:
    driver = ScopeDriver(config=_scope_driver_config(request))
    try:
        result = await asyncio.to_thread(driver.check_connection)
    finally:
        driver.close()

    await terminal_broadcast_hub.broadcast(_format_driver_result("scope_idn", result))
    return serialize_driver_result(result)


@router.post("/scope/channel")
async def scope_channel(request: ScopeChannelRequest) -> dict[str, Any]:
    driver = ScopeDriver(config=_scope_driver_config(request))
    try:
        connect_result = await asyncio.to_thread(driver.connect_if_needed)
        if not connect_result.success:
            result = connect_result
        else:
            result = await asyncio.to_thread(
                driver.set_channel,
                request.channel,
                enabled=request.enabled,
                scale=request.scale,
                offset=request.offset,
                coupling=request.coupling,
            )
    finally:
        driver.close()

    await terminal_broadcast_hub.broadcast(_format_driver_result("scope_set_channel", result))
    return serialize_driver_result(result)


@router.post("/scope/measure")
async def scope_measure(request: ScopeMeasureRequest) -> dict[str, Any]:
    driver = ScopeDriver(config=_scope_driver_config(request))
    try:
        connect_result = await asyncio.to_thread(driver.connect_if_needed)
        if not connect_result.success:
            result = connect_result
        else:
            result = await asyncio.to_thread(
                driver.read_measurement,
                request.channel,
                request.measure,
            )
            if result.success:
                result = _scope_measure_with_expected(result, request)
    finally:
        driver.close()

    await terminal_broadcast_hub.broadcast(_format_driver_result("scope_measure", result))
    return serialize_driver_result(result)


@router.post("/scope/waveform")
async def scope_waveform(request: ScopeWaveformRequest) -> dict[str, Any]:
    config = {
        **_scope_driver_config(request),
        "waveform_points": request.points,
        "waveform_preview_points": request.preview_points,
    }
    driver = ScopeDriver(config=config)
    try:
        connect_result = await asyncio.to_thread(driver.connect_if_needed)
        if not connect_result.success:
            result = connect_result
        else:
            result = await asyncio.to_thread(
                driver.read_waveform,
                request.channel,
                binary=request.binary,
                waveform_format=request.waveform_format,
                datatype=request.datatype,
            )
    finally:
        driver.close()

    await terminal_broadcast_hub.broadcast(_format_driver_result("scope_waveform", result))
    return serialize_driver_result(result)


@router.post("/manual/execute")
async def execute_manual(request: ManualExecuteRequest) -> dict[str, Any]:
    await terminal_broadcast_hub.broadcast(
        f"\r\n[{request.action}] execution started\r\n",
    )
    try:
        result = await asyncio.to_thread(
            execute_manual_action,
            request,
            _stream_manual_output,
        )
    except Exception as exc:  # noqa: BLE001
        result = DriverResult.fail(
            message="manual execution crashed",
            stderr=str(exc),
            returncode=1,
        )
    await _broadcast_manual_result(request.action, result)
    return serialize_driver_result(result)


@router.websocket("/ws/terminal")
async def terminal_monitor(websocket: WebSocket) -> None:
    await websocket.accept()
    broadcast_queue = await terminal_broadcast_hub.register()

    master_fd, slave_fd = pty.openpty()
    shell = os.environ.get("SHELL", "/bin/bash")
    process = subprocess.Popen(  # noqa: S603
        [shell, "-i"],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=os.getcwd(),
        close_fds=True,
        text=False,
    )
    os.close(slave_fd)

    async def forward_terminal_output() -> None:
        try:
            while True:
                chunk = await asyncio.to_thread(os.read, master_fd, 4096)
                if not chunk:
                    break
                await websocket.send_text(
                    chunk.decode("utf-8", errors="replace"),
                )
        except OSError:
            pass

    async def forward_broadcast_output() -> None:
        try:
            while True:
                message = await broadcast_queue.get()
                await websocket.send_text(message)
        except WebSocketDisconnect:
            pass

    output_task = asyncio.create_task(forward_terminal_output())
    broadcast_task = asyncio.create_task(forward_broadcast_output())

    try:
        await websocket.send_text(
            f"Connected to backend shell: {shell}\r\n",
        )
        while True:
            message = await websocket.receive_text()
            os.write(master_fd, message.encode("utf-8"))
    except WebSocketDisconnect:
        pass
    finally:
        output_task.cancel()
        broadcast_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await output_task
        with contextlib.suppress(asyncio.CancelledError):
            await broadcast_task
        await terminal_broadcast_hub.unregister(broadcast_queue)
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            with contextlib.suppress(ProcessLookupError, subprocess.TimeoutExpired):
                process.wait(timeout=1)
        with contextlib.suppress(OSError):
            os.close(master_fd)


@router.websocket("/ws/uart")
async def uart_monitor(websocket: WebSocket) -> None:
    await websocket.accept()
    session = UartMonitorSession(websocket)

    try:
        await websocket.send_json({"type": "status", "state": "ready"})
        while True:
            message = await websocket.receive_json()
            try:
                await session.handle(message)
            except Exception as exc:  # noqa: BLE001
                await session.send_error(f"uart session error: {exc}")
    except WebSocketDisconnect:
        pass
    finally:
        await session.cleanup()


async def _broadcast_manual_result(action: str, result: Any) -> None:
    payloads = []
    data = result.data if hasattr(result, "data") else None

    if action == "program_all" and isinstance(data, dict):
        bit_result = data.get("bit_result")
        elf_result = data.get("elf_result")
        if isinstance(bit_result, dict):
            payloads.append(_format_serialized_result("program_bit", bit_result))
        if isinstance(elf_result, dict):
            payloads.append(_format_serialized_result("program_elf", elf_result))
    else:
        payloads.append(_format_driver_result(action, result))

    for payload in payloads:
        await terminal_broadcast_hub.broadcast(payload)


def _format_driver_result(label: str, result: Any) -> str:
    return _format_serialized_result(
        label,
        {
            "success": result.success,
            "message": result.message,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        },
    )


def _format_serialized_result(label: str, result: dict[str, Any]) -> str:
    lines = [
        "",
        f"[{label}] success={result.get('success')} returncode={result.get('returncode')}",
        f"message: {result.get('message') or ''}",
    ]

    stdout = (result.get("stdout") or "").strip()
    stderr = (result.get("stderr") or "").strip()

    if stdout:
        lines.extend(
            [
                "stdout:",
                stdout,
            ],
        )

    if stderr:
        lines.extend(
            [
                "stderr:",
                stderr,
            ],
        )

    lines.append("")
    return "\r\n".join(lines)


def _stream_manual_output(label: str, channel: str, chunk: str) -> None:
    prefix = "" if channel == "stdout" else "[stderr] "
    terminal_broadcast_hub.broadcast_from_sync(f"{prefix}{chunk}")


def _upload_filename(request: Request) -> str:
    filename = request.query_params.get("filename", "").strip()
    if not filename:
        filename = request.headers.get("x-filename", "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    safe_name = Path(filename).name
    if safe_name in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="invalid filename")
    return safe_name


def _safe_upload_path(directory: Path, filename: str) -> Path:
    destination = (directory / filename).resolve()
    try:
        destination.relative_to(directory.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid upload path") from exc
    return destination


def _list_upload_target_files(file_type: str) -> list[dict[str, Any]]:
    target = UPLOAD_TARGETS[file_type]
    directory = target["directory"]
    if not directory.exists():
        return []

    files = [path for path in directory.iterdir() if path.is_file()]
    return [
        {
            "filename": path.name,
            "path": str(path.relative_to(BASE_DIR)),
            "size": path.stat().st_size,
        }
        for path in sorted(files, key=lambda item: item.name)
    ]


def _scope_resource_from_request(request: ScopeControlRequest) -> str:
    if request.scope_ip:
        if request.scope_port is not None:
            return f"TCPIP::{request.scope_ip}::{request.scope_port}::SOCKET"
        return f"TCPIP::{request.scope_ip}::INSTR"
    raise HTTPException(status_code=400, detail="scope resource or scope_ip is required")


def _scope_driver_config(request: ScopeConnectionRequest) -> dict[str, Any]:
    return {
        "resource": request.resource or _scope_resource_from_ip(request.ip, request.port),
        "visa_backend": request.visa_backend or "@py",
        "timeout_ms": request.timeout_ms,
    }


def _scope_resource_from_ip(ip: str, port: int | None) -> str:
    cleaned_ip = str(ip).strip()
    if not cleaned_ip:
        raise HTTPException(status_code=400, detail="scope ip is required")
    if port is not None:
        return f"TCPIP::{cleaned_ip}::{port}::SOCKET"
    return f"TCPIP::{cleaned_ip}::INSTR"


def _scope_measure_with_expected(
    result: DriverResult,
    request: ScopeMeasureRequest,
) -> DriverResult:
    data = dict(result.data or {})
    value = data.get("value")
    expected = request.expected
    status = "unknown"

    if expected is not None and (expected.min is not None or expected.max is not None):
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            status = "error"
        else:
            lower_ok = expected.min is None or numeric_value >= expected.min
            upper_ok = expected.max is None or numeric_value <= expected.max
            status = "passed" if lower_ok and upper_ok else "failed"

    data["status"] = status
    data["expected"] = expected.model_dump(exclude_none=True) if expected else {}
    unit = data.get("unit") or ""
    message = f"{request.measure} = {value} {unit}".strip()
    if status == "passed":
        message = f"{message} (PASS)"
    elif status == "failed":
        message = f"{message} (FAIL)"

    return DriverResult.ok(
        message=message,
        data=data,
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )


def _validate_step_payload_or_400(payload: TestStepPayload) -> None:
    try:
        validate_step_payload(
            step_type=payload.step_type,
            config_json=payload.config_json,
            expected_json=payload.expected_json,
            timeout_ms=payload.timeout_ms,
        )
    except StepSchemaError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
