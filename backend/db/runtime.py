from __future__ import annotations

import asyncio

from tortoise import Tortoise

from backend.db.config import TORTOISE_ORM
from backend.db.schema_compat import ensure_mvp_schema


_init_lock = asyncio.Lock()


async def ensure_tortoise_ready() -> None:
    if Tortoise._inited:
        return

    async with _init_lock:
        if Tortoise._inited:
            return
        await Tortoise.init(config=TORTOISE_ORM)
        ensure_mvp_schema()
