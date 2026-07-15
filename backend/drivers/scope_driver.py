from __future__ import annotations

import time
import re
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

    def check_connection(self) -> DriverResult:
        """
        检查设备是否可连通，并返回基础身份信息。
        """
        connect_result = self.connect_if_needed()
        if not connect_result.success:
            return connect_result

        idn_result = self.get_identity()
        if not idn_result.success:
            return self.fail(
                message="scope connection check failed",
                stderr=idn_result.stderr or idn_result.message,
            )

        return self.ok(
            message="scope connection check passed",
            data={
                "resource": self.get_config("resource"),
                "idn": str(idn_result.stdout).strip(),
            },
            stdout=idn_result.stdout,
        )

    def read_measurement(self, channel: str, measure: str) -> DriverResult:
        """
        读取单个测量值，例如 FREQ / VPP / VRMS。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            normalized_channel = self._normalize_channel(channel)
        except ValueError as exc:
            return self.fail(str(exc), stderr=str(exc))
        normalized_measure = str(measure).strip().lower()
        if not normalized_measure:
            return self.fail("scope measurement type is required")

        attempted: list[dict[str, str]] = []
        successful_result: DriverResult | None = None
        successful_command = ""
        raw_value = ""
        value: float | None = None

        for command in self._measurement_commands(normalized_channel, normalized_measure):
            result = self.query(command)
            raw_value = str(result.stdout).strip()
            if not result.success:
                attempted.append(
                    {
                        "command": command,
                        "stderr": result.stderr or result.message,
                    },
                )
                continue

            parsed_value = self._parse_measurement_value(raw_value)
            try:
                value = float(parsed_value)
            except (TypeError, ValueError):
                attempted.append(
                    {
                        "command": command,
                        "stdout": raw_value,
                        "stderr": "non-numeric measurement response",
                    },
                )
                continue

            successful_result = result
            successful_command = command
            break

        if successful_result is None or value is None:
            return self.fail(
                message=f"scope measurement failed for {normalized_channel} {normalized_measure}",
                data={
                    "channel": normalized_channel,
                    "measure": normalized_measure,
                    "attempted": attempted,
                },
                stderr="; ".join(
                    item.get("stderr", "") for item in attempted if item.get("stderr")
                ),
            )

        return self.ok(
            message="scope measurement read completed",
            data={
                "channel": normalized_channel,
                "measure": normalized_measure,
                "value": value,
                "unit": self._measurement_unit(normalized_measure),
                "raw": raw_value,
                "command": successful_command,
                "attempted": attempted,
            },
            stdout=str(value),
            stderr=successful_result.stderr,
        )

    def read_voltage(self, channel: str, measurement: str = "VPP") -> DriverResult:
        """
        读取电压类测量值，默认返回峰峰值电压 VPP。
        """
        return self.read_measurement(channel, measurement)

    def read_frequency(self, channel: str) -> DriverResult:
        """
        读取当前通道频率。
        """
        return self.read_measurement(channel, "freq")

    def set_channel(
        self,
        channel: str,
        *,
        enabled: bool = True,
        scale: float = 0.5,
        offset: float = 0,
        coupling: str = "DC",
    ) -> DriverResult:
        """
        配置鼎阳/Siglent 通道的基础垂直参数。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            normalized_channel = self._normalize_channel(channel)
        except ValueError as exc:
            return self.fail(str(exc), stderr=str(exc))

        try:
            numeric_scale = float(scale)
            numeric_offset = float(offset)
        except (TypeError, ValueError) as exc:
            return self.fail("scope channel scale/offset must be numeric", stderr=str(exc))

        if numeric_scale <= 0:
            return self.fail("scope channel scale must be greater than 0")

        normalized_coupling = str(coupling).strip().upper()
        if normalized_coupling not in {"DC", "AC", "GND"}:
            return self.fail("scope coupling must be DC, AC, or GND")

        channel_index = self._channel_index(normalized_channel)
        commands = [
            f"C{channel_index}:TRA {'ON' if enabled else 'OFF'}",
            f"C{channel_index}:CPL {normalized_coupling}",
            f"C{channel_index}:VDIV {numeric_scale}",
            f"C{channel_index}:OFST {numeric_offset}",
        ]

        for command in commands:
            result = self.write(command)
            if not result.success:
                return result

        return self.ok(
            message="scope channel configured",
            data={
                "channel": normalized_channel,
                "enabled": enabled,
                "scale": numeric_scale,
                "offset": numeric_offset,
                "coupling": normalized_coupling,
                "commands": commands,
            },
        )

    def read_waveform(
        self,
        channel: str,
        *,
        binary: bool = True,
        waveform_format: str = "BYTE",
        datatype: str = "B",
    ) -> DriverResult:
        """
        读取当前通道波形数据。
        """
        connection_error = self.ensure_connected()
        if connection_error is not None:
            return connection_error

        try:
            normalized_channel = self._normalize_channel(channel)
        except ValueError as exc:
            return self.fail(str(exc), stderr=str(exc))
        channel_index = self._channel_index(normalized_channel)
        source_command = self.get_config("waveform_source_command")
        format_command = self.get_config("waveform_format_command")
        data_command = self.get_config("waveform_data_command")
        points_command = self.get_config("waveform_points_command")
        points_value = int(float(self.get_config("waveform_points", 1200)))
        preview_points = int(float(self.get_config("waveform_preview_points", 240)))
        commands: list[str] = []

        if source_command:
            commands.append(source_command.format(channel=normalized_channel, channel_index=channel_index))
        if format_command:
            commands.append(format_command.format(format=str(waveform_format).strip().upper()))
        if points_command:
            commands.append(points_command.format(points=points_value))

        if not commands and self.get_config("waveform_preset", "siglent") == "siglent":
            commands.extend(
                [
                    f"WFSU SP,0,NP,{points_value},FP,0",
                    f"C{channel_index}:WF? DAT2",
                ],
            )
        elif data_command:
            commands.append(data_command.format(channel=normalized_channel, channel_index=channel_index))
        else:
            commands.extend(
                [
                    f":WAV:SOUR {normalized_channel}",
                    f":WAV:FORM {str(waveform_format).strip().upper()}",
                    f":WAV:POIN {points_value}",
                    ":WAV:DATA?",
                ],
            )

        for command in commands[:-1]:
            write_result = self.write(command)
            if not write_result.success:
                return write_result

        if binary:
            data_command_to_send = commands[-1]
            data_result = self.query_binary_values(
                data_command_to_send,
                datatype=datatype,
                container=list,
            )
            if not data_result.success:
                return data_result
            waveform_data = [float(item) for item in list(data_result.data or [])]
            preview = self._downsample_waveform(waveform_data, preview_points)
            return self.ok(
                message="scope waveform read completed",
                data={
                    "channel": normalized_channel,
                    "format": str(waveform_format).strip().upper(),
                    "encoding": "binary",
                    "points": len(waveform_data),
                    "preview_points": len(preview),
                    "preview": preview,
                    "command": data_command_to_send,
                    "setup_commands": commands[:-1],
                },
            )

        data_command_to_send = commands[-1]
        data_result = self.query(data_command_to_send)
        if not data_result.success:
            return data_result

        payload = str(data_result.stdout)
        waveform_data = self._parse_text_waveform(payload)
        preview = self._downsample_waveform(waveform_data, preview_points)
        return self.ok(
            message="scope waveform read completed",
            data={
                "channel": normalized_channel,
                "format": str(waveform_format).strip().upper(),
                "encoding": "text",
                "points": len(waveform_data),
                "preview_points": len(preview),
                "preview": preview,
                "raw_preview": payload[:2000],
                "command": data_command_to_send,
                "setup_commands": commands[:-1],
            },
            stdout=payload,
        )

    def get_current_waveform(self, channel: str) -> DriverResult:
        """
        兼容业务表述的别名：读取当前波形。
        """
        return self.read_waveform(channel)

    def _cleanup_handles(self) -> None:
        self._instrument = None
        self._resource_manager = None

    def _measurement_commands(self, channel: str, measure: str) -> list[str]:
        template = self.get_config("measurement_command")
        normalized_measure = str(measure).strip().lower()
        if template:
            return [
                template.format(
                    channel=channel,
                    measure=normalized_measure.upper(),
                    siglent_measure=self._siglent_measure(normalized_measure),
                ),
            ]

        channel_index = self._channel_index(channel)
        commands: list[str] = []
        for siglent_measure in self._siglent_measure_aliases(normalized_measure):
            commands.append(f"C{channel_index}:PAVA? {siglent_measure}")

        standard_measure = self._standard_measure(normalized_measure)
        if standard_measure:
            commands.extend(
                [
                    f":MEASure:{standard_measure}? {channel}",
                    f":MEASure:{standard_measure}? C{channel_index}",
                    f":MEASure:{standard_measure}? CHANnel{channel_index}",
                ],
            )

        return list(dict.fromkeys(commands))

    def _measurement_command(self, channel: str, measure: str) -> str:
        return self._measurement_commands(channel, measure)[0]

    def _normalize_channel(self, channel: str) -> str:
        value = str(channel).strip().upper()
        if value in {"1", "2", "3", "4"}:
            value = f"CH{value}"
        if value not in {"CH1", "CH2", "CH3", "CH4"}:
            raise ValueError("scope channel must be CH1, CH2, CH3, or CH4")
        return value

    def _channel_index(self, channel: str) -> str:
        return self._normalize_channel(channel).replace("CH", "")

    def _siglent_measure(self, measure: str) -> str:
        return self._siglent_measure_aliases(measure)[0]

    def _siglent_measure_aliases(self, measure: str) -> list[str]:
        mapping = {
            "vpp": ["PKPK", "VPP", "AMPL"],
            "vmax": ["MAX", "VMAX"],
            "vmin": ["MIN", "VMIN"],
            "vrms": ["RMS", "VRMS"],
            "vavg": ["MEAN", "VAVG"],
            "freq": ["FREQ"],
            "period": ["PER", "PERIOD"],
            "duty": ["DUTY"],
        }
        normalized = str(measure).strip().lower()
        return mapping.get(normalized, [normalized.upper()])

    def _standard_measure(self, measure: str) -> str | None:
        mapping = {
            "vpp": "VPP",
            "vmax": "VMAX",
            "vmin": "VMIN",
            "vrms": "VRMS",
            "vavg": "VAVerage",
            "freq": "FREQuency",
            "period": "PERiod",
            "duty": "PDUTy",
        }
        return mapping.get(str(measure).strip().lower())

    def _measurement_unit(self, measure: str) -> str:
        normalized = str(measure).strip().lower()
        if normalized == "freq":
            return "Hz"
        if normalized == "period":
            return "s"
        if normalized == "duty":
            return "%"
        return "V"

    def _parse_measurement_value(self, raw_value: str) -> str | None:
        cleaned = str(raw_value).strip()
        if not cleaned:
            return None
        numbers = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", cleaned)
        if not numbers:
            return None
        return numbers[-1]

    def _parse_text_waveform(self, payload: str) -> list[float]:
        values: list[float] = []
        for item in str(payload).replace(";", ",").split(","):
            cleaned = item.strip()
            if not cleaned:
                continue
            try:
                values.append(float(cleaned))
            except ValueError:
                continue
        return values

    def _downsample_waveform(self, values: list[float], max_points: int) -> list[float]:
        if max_points <= 0 or len(values) <= max_points:
            return values
        step = len(values) / max_points
        return [values[min(int(index * step), len(values) - 1)] for index in range(max_points)]
