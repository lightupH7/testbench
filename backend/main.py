from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel
from serial.tools import list_ports
from tortoise import Tortoise
import uvicorn

from backend.db.config import DB_PATH, TORTOISE_ORM
from backend.drivers.vivado_driver import VivadoDriver
from backend.db.models import HardwareProfile, TestCase, TestPlan, TestRun
from backend.drivers.jlink_driver import JLinkDriver


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    应用启动时初始化数据库连接，关闭时释放资源。
    """
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas(safe=True)

    try:
        yield
    finally:
        await Tortoise.close_connections()


app = FastAPI(
    title="TestBench Backend",
    description="Hardware testbench backend service.",
    version="0.1.0",
    lifespan=lifespan,
)


class ProgramElfRequest(BaseModel):
    elf_path: str
    method: str = "pylink"
    jtag_speed: int = 4000
    jlink_lib: str | None = None
    jlink_device: str | None = None
    interface: str | None = None
    expected_entry: str | None = None
    flash_base: str | None = None
    rom_init_delay: float | None = None
    program_window_bytes: int | None = None
    progress_words: int | None = None
    program_bitstream: bool = False
    keep_bin: bool = True


class ProgramBitRequest(BaseModel):
    bit_path: str
    hw_target: str | None = None
    device: str | None = None
    vivado_bin: str | None = None
    python_bin: str | None = None
    keep_tcl: bool = False


class AutoProgramRequest(BaseModel):
    bit_path: str
    elf_path: str
    hw_target: str | None = None
    device: str | None = None
    vivado_bin: str | None = None
    vivado_python_bin: str | None = None
    keep_tcl: bool = False
    method: str = "pylink"
    jtag_speed: int = 4000
    jlink_lib: str | None = None
    jlink_device: str | None = None
    interface: str | None = None
    expected_entry: str | None = None
    flash_base: str | None = None
    rom_init_delay: float | None = None
    program_window_bytes: int | None = None
    progress_words: int | None = None
    keep_bin: bool = True


def _build_jlink_driver(request: ProgramElfRequest) -> JLinkDriver:
    return JLinkDriver(
        config={
            "method": request.method,
            "jtag_speed": request.jtag_speed,
            "jlink_lib": request.jlink_lib,
            "jlink_device": request.jlink_device,
            "interface": request.interface,
            "expected_entry": request.expected_entry,
            "flash_base": request.flash_base,
            "rom_init_delay": request.rom_init_delay,
            "program_window_bytes": request.program_window_bytes,
            "progress_words": request.progress_words,
            "program_bitstream": request.program_bitstream,
            "keep_bin": request.keep_bin,
        },
    )


def _build_vivado_driver(request: ProgramBitRequest) -> VivadoDriver:
    return VivadoDriver(
        config={
            "vivado_bin": request.vivado_bin,
            "python_bin": request.python_bin,
            "hw_target": request.hw_target,
            "device": request.device,
            "keep_tcl": request.keep_tcl,
        },
    )


def _serialize_driver_result(result: Any) -> dict[str, Any]:
    return {
        "success": result.success,
        "message": result.message,
        "data": result.data,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _serialize_hardware_profile(profile: HardwareProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "is_default": profile.is_default,
        "created_at": _serialize_datetime(profile.created_at),
        "updated_at": _serialize_datetime(profile.updated_at),
    }


def _serialize_test_case(case: TestCase) -> dict[str, Any]:
    return {
        "id": case.id,
        "name": case.name,
        "type": case.type,
        "description": case.description,
        "config_json": case.config_json,
        "enabled": case.enabled,
        "created_at": _serialize_datetime(case.created_at),
        "updated_at": _serialize_datetime(case.updated_at),
    }


def _serialize_test_plan(plan: TestPlan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "name": plan.name,
        "board": plan.board,
        "description": plan.description,
        "setup_json": plan.setup_json,
        "enabled": plan.enabled,
        "created_at": _serialize_datetime(plan.created_at),
        "updated_at": _serialize_datetime(plan.updated_at),
    }


def _serialize_test_run(run: TestRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "plan_id": run.plan_id,
        "hardware_profile_id": run.hardware_profile_id,
        "name": run.name,
        "status": run.status,
        "result": run.result,
        "selected_case_ids_json": run.selected_case_ids_json,
        "started_at": _serialize_datetime(run.started_at),
        "ended_at": _serialize_datetime(run.ended_at),
        "created_at": _serialize_datetime(run.created_at),
    }


def _serialize_serial_port(port: Any) -> dict[str, Any]:
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


@app.get("/")
async def root() -> dict[str, str]:
    """
    基础欢迎接口。
    """
    return {
        "name": "testbench-backend",
        "status": "ok",
    }


@app.get("/health")
async def health() -> dict[str, Any]:
    """
    健康检查接口。
    """
    return {
        "status": "ok",
        "database": {
            "engine": "sqlite",
            "path": str(DB_PATH),
        },
    }


@app.get("/api/summary")
async def summary() -> dict[str, int]:
    """
    首页概要统计，方便前端先联调。
    """
    return {
        "hardware_profiles": await HardwareProfile.all().count(),
        "test_cases": await TestCase.all().count(),
        "test_plans": await TestPlan.all().count(),
        "test_runs": await TestRun.all().count(),
    }


@app.get("/api/hardware-profiles")
async def list_hardware_profiles() -> list[dict[str, Any]]:
    """
    硬件配置列表。
    """
    profiles = await HardwareProfile.all().order_by("id")
    return [_serialize_hardware_profile(profile) for profile in profiles]


@app.get("/api/test-cases")
async def list_test_cases() -> list[dict[str, Any]]:
    """
    测试用例列表。
    """
    cases = await TestCase.all().order_by("id")
    return [_serialize_test_case(case) for case in cases]


@app.get("/api/test-plans")
async def list_test_plans() -> list[dict[str, Any]]:
    """
    测试计划列表。
    """
    plans = await TestPlan.all().order_by("id")
    return [_serialize_test_plan(plan) for plan in plans]


@app.get("/api/test-runs")
async def list_test_runs() -> list[dict[str, Any]]:
    """
    测试运行记录列表。
    """
    runs = await TestRun.all().order_by("-id")
    return [_serialize_test_run(run) for run in runs]


@app.get("/api/serial-ports")
async def list_serial_ports() -> dict[str, Any]:
    """
    扫描当前主机可见的串口。
    """
    ports = list(list_ports.comports())
    return {
        "count": len(ports),
        "items": [_serialize_serial_port(port) for port in ports],
    }


@app.post("/api/program/elf")
async def program_elf(request: ProgramElfRequest) -> dict[str, Any]:
    """
    通过 J-Link driver 烧录 ELF。
    """
    driver = _build_jlink_driver(request)
    result = driver.program_elf(
        elf_path=request.elf_path,
        method=request.method,
        jtag_speed=request.jtag_speed,
        jlink_lib=request.jlink_lib,
        jlink_device=request.jlink_device,
        interface=request.interface,
        expected_entry=request.expected_entry,
        flash_base=request.flash_base,
        rom_init_delay=request.rom_init_delay,
        program_window_bytes=request.program_window_bytes,
        progress_words=request.progress_words,
        program_bitstream=request.program_bitstream,
        keep_bin=request.keep_bin,
    )
    driver.close()

    return _serialize_driver_result(result)


@app.post("/api/program/bit")
async def program_bit(request: ProgramBitRequest) -> dict[str, Any]:
    """
    通过 Vivado driver 烧录 bit。
    """
    driver = _build_vivado_driver(request)
    result = driver.program_bit(
        bit_path=request.bit_path,
        hw_target=request.hw_target,
        device=request.device,
    )
    driver.close()

    return _serialize_driver_result(result)


@app.post("/api/program/auto")
async def auto_program(request: AutoProgramRequest) -> dict[str, Any]:
    """
    一键自动烧录：先烧 bit，再烧 elf。
    任一步失败都会停止后续流程。
    """
    vivado_request = ProgramBitRequest(
        bit_path=request.bit_path,
        hw_target=request.hw_target,
        device=request.device,
        vivado_bin=request.vivado_bin,
        python_bin=request.vivado_python_bin,
        keep_tcl=request.keep_tcl,
    )
    jlink_request = ProgramElfRequest(
        elf_path=request.elf_path,
        method=request.method,
        jtag_speed=request.jtag_speed,
        jlink_lib=request.jlink_lib,
        jlink_device=request.jlink_device,
        interface=request.interface,
        expected_entry=request.expected_entry,
        flash_base=request.flash_base,
        rom_init_delay=request.rom_init_delay,
        program_window_bytes=request.program_window_bytes,
        progress_words=request.progress_words,
        keep_bin=request.keep_bin,
    )

    bit_result = await program_bit(vivado_request)
    if not bit_result["success"]:
        return {
            "success": False,
            "message": "bit programming failed, elf programming skipped",
            "steps": {
                "bit": bit_result,
                "elf": None,
            },
        }

    elf_result = await program_elf(jlink_request)
    return {
        "success": elf_result["success"],
        "message": (
            "auto programming completed"
            if elf_result["success"]
            else "elf programming failed after bit programming completed"
        ),
        "steps": {
            "bit": bit_result,
            "elf": elf_result,
        },
    }


def main() -> None:
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )


if __name__ == "__main__":
    main()
