from __future__ import annotations

from contextlib import asynccontextmanager
import sqlite3
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles
from tortoise import Tortoise

from backend.api.routes import router as api_router
from backend.core.config import FRONTEND_DIST_DIR, FRONTEND_INDEX_FILE
from backend.db.config import DB_PATH, TORTOISE_ORM
from backend.db.schema_compat import ensure_mvp_schema
from backend.runner.automation import ensure_default_automation_case
from backend.runner.mvp_sqlite import initialize_run_queue


@asynccontextmanager
async def lifespan(_: FastAPI):
    await Tortoise.init(config=TORTOISE_ORM)
    if not _database_has_existing_schema():
        await Tortoise.generate_schemas(safe=True)
    ensure_mvp_schema()
    await ensure_default_automation_case()
    await initialize_run_queue()

    try:
        yield
    finally:
        await Tortoise.close_connections()


def create_app() -> FastAPI:
    app = FastAPI(
        title="TestBench Backend",
        description="Hardware testbench backend service.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(api_router)
    _mount_health_check(app)
    _mount_frontend(app)
    return app


def _database_has_existing_schema() -> bool:
    if not DB_PATH.exists():
        return False

    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(
            "select name from sqlite_master where type = 'table'",
        ).fetchall()

    table_names = {row[0] for row in rows}
    return {"test_cases", "test_runs", "test_logs"}.issubset(table_names)


def _frontend_fallback_response() -> Any:
    if not FRONTEND_DIST_DIR.exists() or not FRONTEND_INDEX_FILE.exists():
        return {
            "name": "testbench-backend",
            "status": "ok",
            "frontend": "not-built",
        }

    return FileResponse(FRONTEND_INDEX_FILE)


def _mount_frontend(app: FastAPI) -> None:
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/")
    async def root() -> Any:
        return _frontend_fallback_response()

    @app.get("/{full_path:path}")
    async def frontend_entry(full_path: str) -> Any:
        if not FRONTEND_DIST_DIR.exists() or not FRONTEND_INDEX_FILE.exists():
            return _frontend_fallback_response()

        requested_path = (FRONTEND_DIST_DIR / full_path).resolve()
        try:
            requested_path.relative_to(FRONTEND_DIST_DIR.resolve())
        except ValueError:
            return FileResponse(FRONTEND_INDEX_FILE)

        if full_path and requested_path.is_file():
            return FileResponse(requested_path)

        return _frontend_fallback_response()


def _mount_health_check(app: FastAPI) -> None:
    @app.get("/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "database": {
                "engine": "sqlite",
                "path": str(DB_PATH),
            },
        }
