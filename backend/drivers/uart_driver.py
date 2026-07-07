from __future__ import annotations

import time
from typing import Any

from .base import BaseDriver, DriverResult

try:
    import serial
    from serial import SerialException
except ImportError:  # pragma: no cover
    serial = None
    SerialException = Exception


class UartDriver(BaseDriver):
    """
    UART 驱动。

    负责串口连接、发送、接收等底层操作，
    不负责业务层的 PASS / FAIL 判断。
    """

    def __init__(self, name: str = "uart", config: dict[str, Any] | None = None):
        super().__init__(name=name, config=config)
        self._serial: Any = None

    def connect(self) -> DriverResult:
        """
        建立串口连接。
        """
        if self.is_connected() and self._serial is not None:
            return self.ok("uart already connected")

        if serial is None:
            return self.fail("pyserial is not installed")

        validation = self.validate_required_config(["port"])
        if validation is not None:
            return validation

        baudrate = int(self.get_config("baudrate", 115200))
        timeout = self.get_config("timeout", 1.0)
        write_timeout = self.get_config("write_timeout", timeout)

        try:
            self._serial = serial.Serial(
                port=self.get_config("port"),
                baudrate=baudrate,
                bytesize=self.get_config("bytesize", serial.EIGHTBITS),
                parity=self.get_config("parity", serial.PARITY_NONE),
                stopbits=self.get_config("stopbits", serial.STOPBITS_ONE),
                timeout=timeout,
                write_timeout=write_timeout,
                xonxoff=self.get_config("xonxoff", False),
                rtscts=self.get_config("rtscts", False),
                dsrdtr=self.get_config("dsrdtr", False),
            )
        except (SerialException, ValueError, OSError) as exc:
            self._serial = None
            self.set_connected(False)
            return self.fail(
                message=f"failed to open uart: {exc}",
                stderr=str(exc),
            )

        self.set_connected(True)
        return self.ok(
            message="uart connected",
            data={
                "port": self.get_config("port"),
                "baudrate": baudrate,
                "timeout": timeout,
            },
        )

    def close(self) -> DriverResult:
        """
        关闭串口连接。
        """
        if self._serial is None:
            self.set_connected(False)
            return self.ok("uart already closed")

        try:
            if self._serial.is_open:
                self._serial.close()
        except (SerialException, OSError) as exc:
            return self.fail(
                message=f"failed to close uart: {exc}",
                stderr=str(exc),
            )
        finally:
            self._serial = None
            self.set_connected(False)

        return self.ok("uart closed")

    def is_connected(self) -> bool:
        """
        以串口对象实际状态为准。
        """
        return bool(self._serial is not None and getattr(self._serial, "is_open", False))

    def write(
        self,
        data: str | bytes,
        encoding: str = "utf-8",
        append_newline: bool = False,
    ) -> DriverResult:
        """
        向串口写入数据。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        payload = self._normalize_output(data=data, encoding=encoding, append_newline=append_newline)

        try:
            written = self._serial.write(payload)
            self._serial.flush()
        except (SerialException, OSError) as exc:
            return self.fail(
                message=f"failed to write uart data: {exc}",
                stderr=str(exc),
            )

        return self.ok(
            message="uart write completed",
            data={
                "written_bytes": written,
                "payload": payload,
            },
        )

    def read(
        self,
        size: int = 1,
        decode: bool = True,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> DriverResult:
        """
        从串口读取固定长度数据。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            raw = self._serial.read(size=size)
        except (SerialException, OSError) as exc:
            return self.fail(
                message=f"failed to read uart data: {exc}",
                stderr=str(exc),
            )

        return self.ok(
            message="uart read completed",
            data=self._decode_bytes(raw, decode=decode, encoding=encoding, errors=errors),
            stdout=self._decode_text(raw, encoding=encoding, errors=errors),
        )

    def readline(
        self,
        decode: bool = True,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> DriverResult:
        """
        读取一行串口输出。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            raw = self._serial.readline()
        except (SerialException, OSError) as exc:
            return self.fail(
                message=f"failed to read uart line: {exc}",
                stderr=str(exc),
            )

        text = self._decode_text(raw, encoding=encoding, errors=errors)
        return self.ok(
            message="uart line read completed",
            data=self._decode_bytes(raw, decode=decode, encoding=encoding, errors=errors),
            stdout=text,
        )

    def read_available(
        self,
        max_size: int = 4096,
        decode: bool = False,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> DriverResult:
        """
        读取当前串口缓冲区里可用的数据。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            waiting = getattr(self._serial, "in_waiting", 0)
            size = max(1, min(int(waiting) if waiting else 1, max_size))
            raw = self._serial.read(size=size)
        except (SerialException, OSError, ValueError) as exc:
            return self.fail(
                message=f"failed to read available uart data: {exc}",
                stderr=str(exc),
            )

        return self.ok(
            message="uart available data read completed",
            data=self._decode_bytes(raw, decode=decode, encoding=encoding, errors=errors),
            stdout=self._decode_text(raw, encoding=encoding, errors=errors),
        )

    def read_until(
        self,
        expected: str | bytes,
        timeout: float | None = None,
        encoding: str = "utf-8",
        errors: str = "replace",
    ) -> DriverResult:
        """
        持续读取直到遇到目标内容或超时。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        target = expected.encode(encoding) if isinstance(expected, str) else expected
        deadline = time.monotonic() + (
            timeout if timeout is not None else float(self.get_config("read_until_timeout", 5.0))
        )
        buffer = bytearray()

        while time.monotonic() < deadline:
            chunk = self._serial.read(size=1)
            if not chunk:
                continue

            buffer.extend(chunk)
            if target in buffer:
                text = self._decode_text(bytes(buffer), encoding=encoding, errors=errors)
                return self.ok(
                    message="uart expected output received",
                    data=bytes(buffer),
                    stdout=text,
                )

        text = self._decode_text(bytes(buffer), encoding=encoding, errors=errors)
        return self.fail(
            message="uart read_until timeout",
            data=bytes(buffer),
            stdout=text,
        )

    def reset_input_buffer(self) -> DriverResult:
        """
        清空接收缓冲区。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            self._serial.reset_input_buffer()
        except (AttributeError, SerialException, OSError) as exc:
            return self.fail(
                message=f"failed to reset input buffer: {exc}",
                stderr=str(exc),
            )

        return self.ok("uart input buffer reset")

    def reset_output_buffer(self) -> DriverResult:
        """
        清空发送缓冲区。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            self._serial.reset_output_buffer()
        except (AttributeError, SerialException, OSError) as exc:
            return self.fail(
                message=f"failed to reset output buffer: {exc}",
                stderr=str(exc),
            )

        return self.ok("uart output buffer reset")

    def _normalize_output(
        self,
        data: str | bytes,
        encoding: str,
        append_newline: bool,
    ) -> bytes:
        if isinstance(data, bytes):
            payload = data
        else:
            payload = data.encode(encoding)

        if append_newline:
            payload += self.get_config("newline", b"\n")

        return payload

    def _decode_bytes(
        self,
        raw: bytes,
        decode: bool,
        encoding: str,
        errors: str,
    ) -> str | bytes:
        if not decode:
            return raw
        return self._decode_text(raw, encoding=encoding, errors=errors)

    def _decode_text(self, raw: bytes, encoding: str, errors: str) -> str:
        return raw.decode(encoding, errors=errors)
