from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


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


class ManualExecuteRequest(BaseModel):
    action: Literal["program_bit", "program_elf", "program_all"]
    hardware_profile_id: int | None = None
    bit_file: str | None = None
    elf_file: str | None = None
    vivado_path: str = "vivado"
    jlink_path: str = "JLinkExe"
    hw_server_url: str | None = None
    device: str | None = None
    interface: str = "JTAG"
    speed: int = 4000
    timeout: int = 120


class CreateTestRunRequest(BaseModel):
    name: str | None = None
    plan_id: int | None = None
    hardware_profile_id: int | None = None
    test_case_id: int | None = None
    selected_case_ids: list[int] | None = None
    config_overrides: dict[str, object] | None = None


class HardwareProfilePayload(BaseModel):
    name: str
    description: str | None = None
    is_default: bool = False
    board_name: str | None = None
    board_serial: str | None = None
    bit_file: str | None = None
    bit_program_channel: str | None = None
    elf_file: str | None = None
    jlink_serial: str | None = None
    jlink_interface: str | None = None
    jlink_device: str | None = None
    jlink_speed_khz: int | None = None
    uart_port: str | None = None
    uart_baudrate: int = 115200
    uart_bytesize: int = 8
    uart_parity: str = "N"
    uart_stopbits: float = 1.0
    uart_timeout_ms: int = 1000
    scope_model: str | None = None
    scope_ip: str | None = None
    scope_port: int | None = None
    scope_channel: str | None = None


class TestCasePayload(BaseModel):
    name: str
    description: str | None = None
    enabled: bool = True


class TestStepPayload(BaseModel):
    order_index: int
    step_type: str
    name: str
    config_json: dict[str, Any] = Field(default_factory=dict)
    expected_json: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = 30000
