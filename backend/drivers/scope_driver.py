from __future__ import annotations

import time
from typing import Any

from .base import BaseDriver, DriverResult

try:
    import pyvisa
except ImportError:  # pragma: no cover
    pyvisa = None


class ScopeDriver(BaseDriver):
    """
    通用示波器驱动。

    默认基于 VISA + SCPI 指令访问设备，
    支持后续扩展到不同品牌的示波器。
    """

    def __init__(self, name: str = "scope", config: dict[str, Any] | None = None):
        super().__init__(name=name, config=config)
        self._resource_manager: Any = None
        self._instrument: Any = None

    def connect(self) -> DriverResult:
        """
        连接示波器资源。
        """
        if self.is_connected():
            return self.ok("scope already connected")

        if pyvisa is None:
            return self.fail("pyvisa is not installed")

        validation = self.validate_required_config(["resource"])
        if validation is not None:
            return validation

        backend = self.get_config("visa_backend", "@py")
        open_timeout = int(float(self.get_config("timeout_ms", 5000)))

        try:
            self._resource_manager = pyvisa.ResourceManager(backend)
            self._instrument = self._resource_manager.open_resource(self.get_config("resource"))
            self._instrument.timeout = open_timeout
            self._instrument.read_termination = self.get_config("read_termination", "\n")
            self._instrument.write_termination = self.get_config("write_termination", "\n")
            if self.get_config("clear_on_connect", True):
                self._instrument.clear()
        except Exception as exc:
            self._cleanup_handles()
            self.set_connected(False)
            return self.fail(
                message=f"failed to connect scope: {exc}",
                stderr=str(exc),
            )

        self.set_connected(True)

        idn_result = self.query("*IDN?")
        return self.ok(
            message="scope connected",
            data={
                "resource": self.get_config("resource"),
                "idn": idn_result.stdout.strip() if idn_result.success else "",
            },
        )

    def close(self) -> DriverResult:
        """
        关闭示波器连接。
        """
        errors: list[str] = []

        if self._instrument is not None:
            try:
                self._instrument.close()
            except Exception as exc:
                errors.append(f"instrument close failed: {exc}")

        if self._resource_manager is not None:
            try:
                self._resource_manager.close()
            except Exception as exc:
                errors.append(f"resource manager close failed: {exc}")

        self._cleanup_handles()
        self.set_connected(False)

        if errors:
            return self.fail(
                message="failed to close scope cleanly",
                stderr="; ".join(errors),
            )

        return self.ok("scope closed")

    def is_connected(self) -> bool:
        return self._instrument is not None

    def write(self, command: str) -> DriverResult:
        """
        发送 SCPI 命令，不等待返回。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            self._instrument.write(command)
        except Exception as exc:
            return self.fail(
                message=f"failed to write scope command: {exc}",
                stderr=str(exc),
            )

        return self.ok(
            message="scope command sent",
            data={"command": command},
        )

    def read(self) -> DriverResult:
        """
        读取一次设备返回。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            response = self._instrument.read()
        except Exception as exc:
            return self.fail(
                message=f"failed to read scope response: {exc}",
                stderr=str(exc),
            )

        return self.ok(
            message="scope read completed",
            data=response,
            stdout=str(response),
        )

    def query(self, command: str) -> DriverResult:
        """
        发送命令并读取返回。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            response = self._instrument.query(command)
        except Exception as exc:
            return self.fail(
                message=f"failed to query scope: {exc}",
                stderr=str(exc),
            )

        return self.ok(
            message="scope query completed",
            data=response,
            stdout=str(response),
        )

    def query_binary_values(
        self,
        command: str,
        datatype: str = "B",
        container: Any = list,
    ) -> DriverResult:
        """
        读取二进制波形或采样数据。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            values = self._instrument.query_binary_values(
                command,
                datatype=datatype,
                container=container,
            )
        except Exception as exc:
            return self.fail(
                message=f"failed to read scope binary data: {exc}",
                stderr=str(exc),
            )

        return self.ok(
            message="scope binary query completed",
            data=values,
        )

    def reset(self) -> DriverResult:
        """
        复位示波器。
        """
        return self.write("*RST")

    def clear_status(self) -> DriverResult:
        """
        清除设备状态。
        """
        return self.write("*CLS")

    def wait_for_operation_complete(self, timeout: float | None = None) -> DriverResult:
        """
        轮询 *OPC?，等待设备完成当前操作。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        deadline = time.monotonic() + (
            timeout if timeout is not None else float(self.get_config("opc_timeout", 10.0))
        )

        while time.monotonic() < deadline:
            result = self.query("*OPC?")
            if result.success and str(result.stdout).strip() == "1":
                return self.ok("scope operation completed")
            time.sleep(float(self.get_config("opc_poll_interval", 0.1)))

        return self.fail("scope operation wait timeout")

    def list_resources(self) -> DriverResult:
        """
        枚举当前可见的 VISA 资源。
        """
        if pyvisa is None:
            return self.fail("pyvisa is not installed")

        backend = self.get_config("visa_backend", "@py")

        try:
            with pyvisa.ResourceManager(backend) as resource_manager:
                resources = list(resource_manager.list_resources())
        except Exception as exc:
            return self.fail(
                message=f"failed to list scope resources: {exc}",
                stderr=str(exc),
            )

        return self.ok(
            message="scope resources listed",
            data=resources,
        )

    def get_identity(self) -> DriverResult:
        """
        读取设备 IDN 信息。
        """
        return self.query("*IDN?")

    def _cleanup_handles(self) -> None:
        self._instrument = None
        self._resource_manager = None
