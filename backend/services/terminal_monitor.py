from __future__ import annotations

import asyncio


class TerminalBroadcastHub:
    def __init__(self) -> None:
        self._queues: dict[asyncio.Queue[str], asyncio.AbstractEventLoop] = {}
        self._lock = asyncio.Lock()

    async def register(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        async with self._lock:
            self._queues[queue] = loop
        return queue

    async def unregister(self, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._queues.pop(queue, None)

    async def broadcast(self, message: str) -> None:
        async with self._lock:
            queue_items = tuple(self._queues.items())
        for queue, _ in queue_items:
            await queue.put(message)

    def broadcast_from_sync(self, message: str) -> None:
        queue_items = tuple(self._queues.items())
        for queue, loop in queue_items:
            loop.call_soon_threadsafe(queue.put_nowait, message)


terminal_broadcast_hub = TerminalBroadcastHub()
