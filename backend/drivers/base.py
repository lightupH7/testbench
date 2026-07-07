from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import subprocess
import threading
from typing import Any, Iterable


@dataclass
class DriverResult:
    """
    所有 Driver 的统一返回结果。
    """

    success: bool
    message: str = ""
    data: Any = None
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None

    @classmethod
    def ok(cls, message: str = "", **kwargs: Any) -> "DriverResult":
        """
        快速构造成功结果。
        """
        return cls(success=True, message=message, **kwargs)

    @classmethod
    def fail(cls, message: str = "", **kwargs: Any) -> "DriverResult":
        """
        快速构造失败结果。
        """
        return cls(success=False, message=message, **kwargs)


class BaseDriver(ABC):
    """
    所有 Driver 的基类。

    Driver 只负责底层操作：
    - UART 串口收发
    - Vivado 烧录 bit
    - J-Link 脚本烧录 elf
    - 示波器/电源等仪器控制

    Driver 不负责判断 PASS / FAIL。
    PASS / FAIL 放在 Case 层。
    """

    def __init__(self, name: str, config: dict[str, Any] | None = None):
        self.name = name
        self.config = config or {}
        self._connected = False

    @abstractmethod
    def connect(self) -> DriverResult:
        """
        连接设备，或者准备工具环境。
        """
        raise NotImplementedError

    @abstractmethod
    def close(self) -> DriverResult:
        """
        关闭设备，释放资源。
        """
        raise NotImplementedError

    def is_connected(self) -> bool:
        """
        是否已连接。

        子类可以重写。
        """
        return self._connected

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        安全读取配置。
        """
        return self.config.get(key, default)

    def set_connected(self, connected: bool) -> None:
        """
        统一维护连接状态，便于子类复用。
        """
        self._connected = connected

    def ensure_connected(self) -> DriverResult | None:
        """
        在执行实际操作前检查连接状态。
        """
        if self.is_connected():
            return None
        return self.fail("driver is not connected")

    def validate_required_config(self, keys: Iterable[str]) -> DriverResult | None:
        """
        检查必要配置项是否存在且非空。
        """
        missing_keys = [
            key
            for key in keys
            if key not in self.config or self.config[key] in (None, "")
        ]
        if not missing_keys:
            return None
        return self.fail(
            message=f"missing required config: {', '.join(missing_keys)}",
            data={"missing_keys": missing_keys},
        )

    def connect_if_needed(self) -> DriverResult:
        """
        懒连接辅助方法，避免重复 connect。
        """
        if self.is_connected():
            return self.ok("driver already connected")
        result = self.connect()
        if result.success and not self.is_connected():
            self.set_connected(True)
        return result

    def safe_call(self, action: str, func: Any, *args: Any, **kwargs: Any) -> DriverResult:
        """
        用统一格式包装子类的底层调用异常。
        """
        try:
            result = func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            return self.fail(
                message=f"{action} failed: {exc}",
                stderr=str(exc),
            )

        if isinstance(result, DriverResult):
            return result

        return self.ok(
            message=f"{action} completed",
            data=result,
        )

    def run_command_streaming(
        self,
        command: list[str],
        *,
        timeout: float | None = None,
        on_output: Any = None,
    ) -> tuple[str, str, int]:
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        process = subprocess.Popen(  # noqa: S603
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        def reader(stream: Any, target: list[str], channel: str) -> None:
            try:
                for line in iter(stream.readline, ""):
                    target.append(line)
                    if on_output is not None:
                        on_output(channel, line)
            finally:
                stream.close()

        stdout_thread = threading.Thread(
            target=reader,
            args=(process.stdout, stdout_chunks, "stdout"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=reader,
            args=(process.stderr, stderr_chunks, "stderr"),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            raise

        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        return ("".join(stdout_chunks), "".join(stderr_chunks), returncode)

    def ok(self, message: str = "", **kwargs: Any) -> DriverResult:
        """
        子类中构造成功结果的便捷入口。
        """
        return DriverResult.ok(message=message, **kwargs)

    def fail(self, message: str = "", **kwargs: Any) -> DriverResult:
        """
        子类中构造失败结果的便捷入口。
        """
        return DriverResult.fail(message=message, **kwargs)

    def __enter__(self) -> "BaseDriver":
        """
        支持 with 语法自动建立连接。
        """
        result = self.connect_if_needed()
        if not result.success:
            raise RuntimeError(result.message or f"failed to connect driver {self.name}")
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        """
        退出 with 时尽力释放资源，不吞掉业务异常。
        """
        self.safe_call("close", self.close)
        return False
