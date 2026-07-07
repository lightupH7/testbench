from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseDriver, DriverResult


class VivadoDriver(BaseDriver):
    """
    Vivado 烧录驱动。

    负责调用 Vivado batch 模式执行 TCL，
    不负责业务层测试结果判定。
    """

    def __init__(self, name: str = "vivado", config: dict[str, Any] | None = None):
        super().__init__(name=name, config=config)
        self._connected = False

    def connect(self) -> DriverResult:
        """
        检查 Vivado 可执行文件和 Python 烧录脚本是否可用。
        """
        vivado_bin = self._resolve_vivado_bin()
        if vivado_bin is None:
            self.set_connected(False)
            return self.fail("vivado executable not found")

        python_bin = self._resolve_python_bin()
        if python_bin is None:
            self.set_connected(False)
            return self.fail("python executable not found for vivado flow")

        program_script = self._resolve_program_script()
        if not program_script.exists():
            self.set_connected(False)
            return self.fail(
                message="vivado program script not found",
                data={"script": str(program_script)},
            )

        self.set_connected(True)
        return self.ok(
            message="vivado environment ready",
            data={
                "vivado_bin": str(vivado_bin),
                "python_bin": str(python_bin),
                "program_script": str(program_script),
            },
        )

    def close(self) -> DriverResult:
        """
        Vivado batch 模式无持久连接，这里只重置状态。
        """
        self.set_connected(False)
        return self.ok("vivado driver closed")

    def program_bit(
        self,
        bit_path: str | Path,
        *,
        vivado_bin: str | None = None,
        hw_target: str | None = None,
        device: str | None = None,
        hw_server_url: str | None = None,
        timeout: int | None = None,
        on_output: Any = None,
    ) -> DriverResult:
        """
        调用 Vivado TCL 脚本烧录 bit 文件。
        """
        ready = self.connect_if_needed()
        if not ready.success:
            return ready

        bit_file = Path(bit_path).expanduser().resolve()
        if not bit_file.exists():
            return self.fail(
                message="bit file not found",
                data={"bit_path": str(bit_file)},
            )

        command = self._build_program_command(
            bit_path=bit_file,
            vivado_bin=vivado_bin or self.get_config("vivado_bin"),
            hw_target=hw_target or self.get_config("hw_target", ""),
            device=device or self.get_config("device", ""),
            hw_server_url=hw_server_url or self.get_config("hw_server_url"),
        )

        resolved_timeout = timeout if timeout is not None else self.get_config("timeout")

        try:
            stdout_text, stderr_text, returncode = self.run_command_streaming(
                command,
                timeout=resolved_timeout,
                on_output=on_output,
            )
        except subprocess.TimeoutExpired as exc:
            return self.fail(
                message="vivado program bit timeout",
                data={"command": command, "bit_path": str(bit_file)},
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            )
        except OSError as exc:
            return self.fail(
                message=f"failed to launch vivado: {exc}",
                stderr=str(exc),
            )

        result_data = {
            "command": command,
            "bit_path": str(bit_file),
            "hw_target": hw_target or self.get_config("hw_target", ""),
            "device": device or self.get_config("device", ""),
            "hw_server_url": hw_server_url or self.get_config("hw_server_url"),
            "program_script": str(self._resolve_program_script()),
        }

        if returncode != 0:
            return self.fail(
                message="vivado program bit failed",
                data=result_data,
                stdout=stdout_text,
                stderr=stderr_text,
                returncode=returncode,
            )

        return self.ok(
            message="vivado program bit completed",
            data=result_data,
            stdout=stdout_text,
            stderr=stderr_text,
            returncode=returncode,
        )

    def _resolve_vivado_bin(self, configured: str | Path | None = None) -> Path | None:
        configured = configured or self.get_config("vivado_bin")
        if configured:
            configured_str = str(configured)
            has_path_hint = any(separator in configured_str for separator in ("/", "\\"))
            if has_path_hint:
                return Path(configured_str).expanduser().resolve()

            found = shutil.which(configured_str)
            if found is None:
                return None
            return Path(found).resolve()

        found = shutil.which("vivado")
        if found is None:
            return None
        return Path(found).resolve()

    def _resolve_tcl_script(self) -> Path:
        configured = self.get_config("tcl_script")
        if configured:
            return Path(configured).expanduser().resolve()

        return Path(__file__).resolve().parents[1] / "scripts" / "program_bit.tcl"

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

        return Path(__file__).resolve().parents[1] / "scripts" / "program_bit.py"

    def _build_program_command(
        self,
        bit_path: Path,
        vivado_bin: str | Path | None,
        hw_target: str,
        device: str,
        hw_server_url: str | None,
    ) -> list[str]:
        python_bin = self._resolve_python_bin()
        resolved_vivado_bin = self._resolve_vivado_bin(vivado_bin)
        program_script = self._resolve_program_script()
        if python_bin is None:
            raise RuntimeError("python executable not resolved")
        if resolved_vivado_bin is None:
            raise RuntimeError("vivado executable not resolved")

        command = [
            str(python_bin),
            "-u",
            str(program_script),
            "--vivado-bin",
            str(resolved_vivado_bin),
            "--bit",
            str(bit_path),
        ]
        if hw_target:
            command.extend(["--hw-target", hw_target])
        if device:
            command.extend(["--device", device])
        if hw_server_url:
            command.extend(["--hw-server-url", hw_server_url])
        if self.get_config("keep_tcl", False):
            command.append("--keep-tcl")
        return command
