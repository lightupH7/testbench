from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


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
        return False

    def get_config(self, key: str, default: Any = None) -> Any:
        """
        安全读取配置。
        """
        return self.config.get(key, default)