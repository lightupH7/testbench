from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist" / "spa"
FRONTEND_INDEX_FILE = FRONTEND_DIST_DIR / "index.html"
