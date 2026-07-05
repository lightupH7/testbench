from __future__ import annotations

from typing import Any

from backend.drivers.jlink_driver import JLinkDriver
from backend.drivers.scope_driver import ScopeDriver
from backend.drivers.uart_driver import UartDriver
from backend.drivers.vivado_driver import VivadoDriver


class ResourceManager:
    """
    最小资源管理器。

    先负责保存资源配置，并按名称创建对应 driver。
    后续如果要做资源锁、占用状态、并发仲裁，可以继续加在这里。
    """

    def __init__(self, resources: dict[str, dict[str, Any]] | None = None):
        self._resources = resources or {}

    def register_resource(self, name: str, resource_type: str, config: dict[str, Any]) -> None:
        self._resources[name] = {
            "type": resource_type,
            "config": dict(config),
        }

    def get_resource_config(self, name: str) -> dict[str, Any]:
        resource = self._resources.get(name)
        if resource is None:
            raise KeyError(f"resource not found: {name}")
        return dict(resource["config"])

    def create_driver(self, name: str):
        resource = self._resources.get(name)
        if resource is None:
            raise KeyError(f"resource not found: {name}")

        resource_type = resource["type"]
        config = dict(resource["config"])

        if resource_type == "uart":
            return UartDriver(name=name, config=config)
        if resource_type == "scope":
            return ScopeDriver(name=name, config=config)
        if resource_type == "jlink":
            return JLinkDriver(name=name, config=config)
        if resource_type == "vivado":
            return VivadoDriver(name=name, config=config)

        raise ValueError(f"unsupported resource type: {resource_type}")

    def create_vivado_driver(self, name: str) -> VivadoDriver:
        driver = self.create_driver(name)
        if not isinstance(driver, VivadoDriver):
            raise TypeError(f"resource {name} is not a vivado driver")
        return driver

    def create_jlink_driver(self, name: str) -> JLinkDriver:
        driver = self.create_driver(name)
        if not isinstance(driver, JLinkDriver):
            raise TypeError(f"resource {name} is not a jlink driver")
        return driver

    def list_resources(self, resource_type: str | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for name, resource in self._resources.items():
            if resource_type is not None and resource["type"] != resource_type:
                continue
            items.append(
                {
                    "name": name,
                    "type": resource["type"],
                    "config": dict(resource["config"]),
                }
            )
        return items
