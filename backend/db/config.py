from pathlib import Path


# 当前文件位置：
# TESTBENCH/backend/db/config.py
#
# parents[0] = TESTBENCH/backend/db
# parents[1] = TESTBENCH/backend
# parents[2] = TESTBENCH
BASE_DIR = Path(__file__).resolve().parents[2]

# SQLite 数据库文件：
# TESTBENCH/database/testbench.db
DB_PATH = BASE_DIR / "database" / "testbench.db"


TORTOISE_ORM = {
    "connections": {
        "default": f"sqlite://{DB_PATH}",
    },
    "apps": {
        "models": {
            # 告诉 Tortoise 去哪里找 Model 类
            "models": ["backend.db.models"],
            "default_connection": "default",
        },
    },
}