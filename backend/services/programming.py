from __future__ import annotations

from backend.api.schemas import ProgramBitRequest, ProgramElfRequest
from backend.drivers.base import DriverResult
from backend.drivers.jlink_driver import JLinkDriver
from backend.drivers.vivado_driver import VivadoDriver


def build_jlink_driver(request: ProgramElfRequest) -> JLinkDriver:
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


def build_vivado_driver(request: ProgramBitRequest) -> VivadoDriver:
    return VivadoDriver(
        config={
            "vivado_bin": request.vivado_bin,
            "python_bin": request.python_bin,
            "hw_target": request.hw_target,
            "device": request.device,
            "keep_tcl": request.keep_tcl,
        },
    )


def program_elf(request: ProgramElfRequest) -> DriverResult:
    driver = build_jlink_driver(request)
    try:
        return driver.program_elf(
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
    finally:
        driver.close()


def program_bit(request: ProgramBitRequest) -> DriverResult:
    driver = build_vivado_driver(request)
    try:
        return driver.program_bit(
            bit_path=request.bit_path,
            hw_target=request.hw_target,
            device=request.device,
        )
    finally:
        driver.close()
