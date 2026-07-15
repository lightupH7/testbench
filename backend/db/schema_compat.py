from __future__ import annotations

import sqlite3

from backend.db.config import DB_PATH


MVP_COLUMNS: dict[str, dict[str, str]] = {
    "hardware_profiles": {
        "board_name": "varchar(100)",
        "board_serial": "varchar(100)",
        "bit_file": "varchar(500)",
        "bit_program_channel": "varchar(100)",
        "elf_file": "varchar(500)",
        "jlink_serial": "varchar(100)",
        "jlink_interface": "varchar(50)",
        "jlink_device": "varchar(100)",
        "jlink_speed_khz": "int",
        "uart_port": "varchar(100)",
        "uart_baudrate": "int default 115200",
        "uart_bytesize": "int default 8",
        "uart_parity": "varchar(20) default 'N'",
        "uart_stopbits": "real default 1.0",
        "uart_timeout_ms": "int default 1000",
        "scope_model": "varchar(100)",
        "scope_ip": "varchar(100)",
        "scope_port": "int",
        "scope_channel": "varchar(50)",
    },
    "test_runs": {
        "test_case_id": "int",
        "summary": "text",
        "error_message": "text",
        "profile_snapshot_json": "text",
        "case_snapshot_json": "text",
        "finished_at": "datetime",
        "duration_ms": "int",
        "total_steps": "int default 0",
        "completed_steps": "int default 0",
        "progress_percent": "int default 0",
        "cancel_requested": "int default 0",
        "current_step_name": "varchar(100)",
    },
    "test_step_results": {
        "test_step_id": "int",
        "order_index": "int default 0",
        "step_name": "varchar(100)",
        "step_type": "varchar(50)",
        "message": "text",
        "stdout": "text",
        "stderr": "text",
        "data_json": "text",
        "finished_at": "datetime",
        "duration_ms": "int",
    },
    "test_steps": {
        "continue_on_failure": "int default 0",
    },
}


def ensure_mvp_schema() -> None:
    if not DB_PATH.exists():
        return

    with sqlite3.connect(DB_PATH) as connection:
        _ensure_test_steps_table(connection)
        for table_name, columns in MVP_COLUMNS.items():
            if not _table_exists(connection, table_name):
                continue
            existing_columns = _column_names(connection, table_name)
            for column_name, column_type in columns.items():
                if column_name in existing_columns:
                    continue
                connection.execute(
                    f"alter table {table_name} add column {column_name} {column_type}",
                )
        connection.commit()


def ensure_mvp_columns() -> None:
    ensure_mvp_schema()


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"pragma table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_test_steps_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        create table if not exists test_steps (
            id integer primary key autoincrement not null,
            order_index int not null default 0,
            step_type varchar(50) not null,
            name varchar(100) not null,
            config_json text not null default '{}',
            expected_json text not null default '{}',
            timeout_ms int not null default 30000,
            continue_on_failure int not null default 0,
            created_at datetime not null default current_timestamp,
            updated_at datetime not null default current_timestamp,
            case_id int not null references test_cases(id) on delete cascade,
            unique(case_id, order_index)
        )
        """,
    )
