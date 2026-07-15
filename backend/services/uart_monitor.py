from __future__ import annotations

import asyncio
import binascii
import contextlib
import time
from typing import Any

from fastapi import WebSocket

from backend.drivers.base import DriverResult
from backend.drivers.uart_driver import UartDriver


TEXT_ENCODING = "utf-8"
READ_CHUNK_SIZE = 4096
MAX_BUFFER_BYTES = 16384
FLUSH_INTERVAL_SECONDS = 0.06


class UartMonitorSession:
    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.driver: UartDriver | None = None
        self._io_lock = asyncio.Lock()
        self._reader_task: asyncio.Task[None] | None = None

    async def handle(self, message: dict[str, Any]) -> None:
        message_type = message.get("type")
        if message_type == "open":
            await self.open(message)
            return
        if message_type == "write":
            await self.write(message)
            return
        if message_type == "close":
            await self.close()
            return
        if message_type == "ping":
            await self.websocket.send_json({"type": "pong", "time": time.time()})
            return

        await self.send_error(f"unsupported uart message type: {message_type}")

    async def open(self, message: dict[str, Any]) -> None:
        port = str(message.get("port") or "").strip()
        if not port:
            await self.send_error("serial port is required")
            return

        await self.close(send_status=False)

        try:
            baudrate = int(message.get("baudrate") or 115200)
            bytesize = int(message.get("bytesize") or 8)
            parity = str(message.get("parity") or "N").upper()
            stopbits = float(message.get("stopbits") or 1.0)
        except (TypeError, ValueError):
            await self.send_error("invalid uart parameters")
            return

        config = {
            "port": port,
            "baudrate": baudrate,
            "bytesize": bytesize,
            "parity": parity,
            "stopbits": stopbits,
            "timeout": 0.05,
            "write_timeout": 1.0,
            "exclusive": bool(message.get("exclusive", True)),
        }
        self.driver = UartDriver(config=config)
        result = await asyncio.to_thread(self.driver.connect)
        await self.send_result("open", result)

        if result.success:
            self._reader_task = asyncio.create_task(self._read_loop())
            return

        self.driver = None
        await self.websocket.send_json({"type": "status", "state": "closed"})

    async def write(self, message: dict[str, Any]) -> None:
        if self.driver is None or not self.driver.is_connected():
            await self.send_error("uart is not connected")
            return

        try:
            payload = parse_payload(
                str(message.get("data") or ""),
                str(message.get("format") or "text"),
            )
        except ValueError as exc:
            await self.send_error(str(exc))
            return

        append_newline = bool(message.get("append_newline", False))
        async with self._io_lock:
            result = await asyncio.to_thread(
                self.driver.write,
                payload,
                TEXT_ENCODING,
                append_newline,
        )
        await self.send_result("write", result)
        if not result.success:
            await self.close(send_status=False)
            await self.websocket.send_json({"type": "status", "state": "closed"})

    async def close(self, *, send_status: bool = True) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self.driver is None:
            if send_status:
                await self.websocket.send_json({"type": "status", "state": "closed"})
            return

        async with self._io_lock:
            result = await asyncio.to_thread(self.driver.close)
        self.driver = None
        if send_status:
            await self.send_result("close", result)

    async def cleanup(self) -> None:
        with contextlib.suppress(Exception):
            await self.close(send_status=False)

    async def _read_loop(self) -> None:
        buffer = bytearray()
        last_flush = time.monotonic()
        should_notify_closed = True
        try:
            while self.driver is not None and self.driver.is_connected():
                async with self._io_lock:
                    result = await asyncio.to_thread(
                        self.driver.read_available,
                        READ_CHUNK_SIZE,
                        False,
                        TEXT_ENCODING,
                        "replace",
                    )

                if not result.success:
                    await self.send_result("read", result)
                    break

                chunk = result.data if isinstance(result.data, bytes) else b""
                if chunk:
                    buffer.extend(chunk)

                now = time.monotonic()
                should_flush = buffer and (
                    len(buffer) >= MAX_BUFFER_BYTES
                    or now - last_flush >= FLUSH_INTERVAL_SECONDS
                )
                if should_flush:
                    await self.send_data(bytes(buffer))
                    buffer.clear()
                    last_flush = now

                if not chunk:
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            should_notify_closed = False
            raise
        except Exception as exc:  # noqa: BLE001
            await self.send_error(f"uart read loop crashed: {exc}")
        finally:
            if buffer:
                await self.send_data(bytes(buffer))
            if self.driver is not None and self.driver.is_connected():
                async with self._io_lock:
                    await asyncio.to_thread(self.driver.close)
                self.driver = None
            if should_notify_closed:
                await self.websocket.send_json({"type": "status", "state": "closed"})

    async def send_data(self, payload: bytes) -> None:
        await self.websocket.send_json(
            {
                "type": "data",
                "size": len(payload),
                "hex": payload.hex(" "),
                "text": payload.decode(TEXT_ENCODING, errors="replace"),
                "timestamp": time.time(),
            },
        )

    async def send_result(self, action: str, result: DriverResult) -> None:
        payload: dict[str, Any] = {
            "type": "result",
            "action": action,
            "success": result.success,
            "message": result.message,
            "timestamp": time.time(),
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
        if result.data is not None:
            payload["data"] = _json_safe(result.data)
        await self.websocket.send_json(payload)

    async def send_error(self, message: str) -> None:
        await self.websocket.send_json(
            {
                "type": "error",
                "success": False,
                "message": message,
            },
        )


def parse_payload(data: str, payload_format: str) -> bytes | str:
    normalized_format = payload_format.lower()
    if normalized_format == "hex":
        normalized = "".join(data.split())
        if not normalized:
            return b""
        try:
            return binascii.unhexlify(normalized)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("hex payload must contain complete byte pairs") from exc

    if normalized_format in {"text", "utf8", "utf-8", "ascii"}:
        return data

    raise ValueError(f"unsupported payload format: {payload_format}")


def _json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {
            "hex": value.hex(" "),
            "text": value.decode(TEXT_ENCODING, errors="replace"),
            "size": len(value),
        }
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value
