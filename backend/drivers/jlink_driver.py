from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseDriver, DriverResult


class JLinkDriver(BaseDriver):
    """
    J-Link 烧录驱动。

    第一版先复用现有 Python 烧录脚本，
    统一由 driver 层对外提供 ELF 烧录能力。
    """

    def __init__(self, name: str = "jlink", config: dict[str, Any] | None = None):
        super().__init__(name=name, config=config)

    def connect(self) -> DriverResult:
        """
        检查 Python 解释器和烧录脚本是否可用。
        """
        python_bin = self._resolve_python_bin()
        if python_bin is None:
            self.set_connected(False)
            return self.fail("python executable not found for jlink flow")

        script_path = self._resolve_program_script()
        if not script_path.exists():
            self.set_connected(False)
            return self.fail(
                message="jlink program script not found",
                data={"script": str(script_path)},
            )

        self.set_connected(True)
        return self.ok(
            message="jlink environment ready",
            data={
                "python_bin": str(python_bin),
                "script": str(script_path),
            },
        )

    def close(self) -> DriverResult:
        """
        脚本式驱动无持久连接，这里只重置状态。
        """
        self.set_connected(False)
        return self.ok("jlink driver closed")

    def program_elf(
        self,
        elf_path: str | Path,
        *,
        jtag_speed: int | None = None,
        jlink_lib: str | None = None,
        jlink_device: str | None = None,
        interface: str | None = None,
        expected_entry: int | str | None = None,
        flash_base: int | str | None = None,
        rom_init_delay: float | None = None,
        program_window_bytes: int | None = None,
        progress_words: int | None = None,
        method: str | None = None,
        program_bitstream: bool | None = None,
        keep_bin: bool | None = None,
    ) -> DriverResult:
        """
        调用 Python 烧录脚本烧录 ELF。
        """
        ready = self.connect_if_needed()
        if not ready.success:
            return ready

        elf_file = Path(elf_path).expanduser().resolve()
        if not elf_file.exists():
            return self.fail(
                message="elf file not found",
                data={"elf_path": str(elf_file)},
            )

        command = self._build_program_command(
            elf_path=elf_file,
            jtag_speed=jtag_speed,
            jlink_lib=jlink_lib,
            jlink_device=jlink_device,
            interface=interface,
            expected_entry=expected_entry,
            flash_base=flash_base,
            rom_init_delay=rom_init_delay,
            program_window_bytes=program_window_bytes,
            progress_words=progress_words,
            method=method,
            program_bitstream=program_bitstream,
            keep_bin=keep_bin,
        )

        timeout = self.get_config("timeout")

        try:
            completed = subprocess.run(  # noqa: S603
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return self.fail(
                message="jlink program elf timeout",
                data={"command": command, "elf_path": str(elf_file)},
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            )
        except OSError as exc:
            return self.fail(
                message=f"failed to launch jlink programmer: {exc}",
                data={"command": command, "elf_path": str(elf_file)},
                stderr=str(exc),
            )

        result_data = {
            "command": command,
            "elf_path": str(elf_file),
            "method": method or self.get_config("method", "pylink"),
            "jtag_speed": jtag_speed if jtag_speed is not None else self.get_config("jtag_speed"),
        }

        if completed.returncode != 0:
            return self.fail(
                message="jlink program elf failed",
                data=result_data,
                stdout=completed.stdout,
                stderr=completed.stderr,
                returncode=completed.returncode,
            )

        return self.ok(
            message="jlink program elf completed",
            data=result_data,
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    def _resolve_python_bin(self) -> Path | None:
        configured = self.get_config("python_bin")
        if configured:
            return Path(configured).expanduser().resolve()

        for candidate in (
            "/home/cmt/work/opentitan/.pixi/envs/default/bin/python",
            shutil.which("python3"),
            shutil.which("python"),
        ):
            if candidate:
                return Path(candidate).resolve()
        return None

    def _resolve_program_script(self) -> Path:
        configured = self.get_config("program_script")
        if configured:
            return Path(configured).expanduser().resolve()
        return Path(__file__).resolve().parents[1] / "scripts" / "program-cw310-zephyr-elf.py"

    def _build_program_command(
        self,
        *,
        elf_path: Path,
        jtag_speed: int | None,
        jlink_lib: str | None,
        jlink_device: str | None,
        interface: str | None,
        expected_entry: int | str | None,
        flash_base: int | str | None,
        rom_init_delay: float | None,
        program_window_bytes: int | None,
        progress_words: int | None,
        method: str | None,
        program_bitstream: bool | None,
        keep_bin: bool | None,
    ) -> list[str]:
        python_bin = self._resolve_python_bin()
        if python_bin is None:
            raise RuntimeError("python executable not resolved")

        script_path = self._resolve_program_script()
        resolved_method = method or self.get_config("method", "pylink")

        command = [
            str(python_bin),
            str(script_path),
            "--elf",
            str(elf_path),
            "--method",
            resolved_method,
        ]

        resolved_jtag_speed = jtag_speed if jtag_speed is not None else self.get_config("jtag_speed")
        if resolved_jtag_speed:
            command.extend(["--jtag-speed", str(resolved_jtag_speed)])

        resolved_jlink_lib = jlink_lib or self.get_config("jlink_lib")
        if resolved_jlink_lib:
            command.extend(["--jlink-lib", str(resolved_jlink_lib)])

        resolved_jlink_device = jlink_device or self.get_config("jlink_device")
        if resolved_jlink_device:
            command.extend(["--jlink-device", str(resolved_jlink_device)])

        resolved_interface = interface or self.get_config("interface")
        if resolved_interface:
            command.extend(["--interface", str(resolved_interface)])

        resolved_expected_entry = (
            expected_entry if expected_entry is not None else self.get_config("expected_entry")
        )
        if resolved_expected_entry is not None:
            command.extend(["--expected-entry", str(resolved_expected_entry)])

        resolved_flash_base = flash_base if flash_base is not None else self.get_config("flash_base")
        if resolved_flash_base is not None:
            command.extend(["--flash-base", str(resolved_flash_base)])

        resolved_rom_init_delay = (
            rom_init_delay if rom_init_delay is not None else self.get_config("rom_init_delay")
        )
        if resolved_rom_init_delay is not None:
            command.extend(["--rom-init-delay", str(resolved_rom_init_delay)])

        resolved_window = (
            program_window_bytes
            if program_window_bytes is not None
            else self.get_config("program_window_bytes")
        )
        if resolved_window is not None:
            command.extend(["--program-window-bytes", str(resolved_window)])

        resolved_progress_words = (
            progress_words if progress_words is not None else self.get_config("progress_words")
        )
        if resolved_progress_words is not None:
            command.extend(["--progress-words", str(resolved_progress_words)])

        resolved_program_bitstream = (
            program_bitstream
            if program_bitstream is not None
            else self.get_config("program_bitstream", False)
        )
        if resolved_program_bitstream:
            command.append("--program-bitstream")

        resolved_keep_bin = keep_bin if keep_bin is not None else self.get_config("keep_bin", True)
        if not resolved_keep_bin:
            command.append("--no-keep-bin")

        return command
