from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


def get_connection(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def execute_query(database_path: Path, sql: str) -> tuple[list[str], list[list[Any]]]:
    with get_connection(database_path) as connection:
        cursor = connection.execute(sql)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description or []]
        materialized_rows = [[row[column] for column in columns] for row in rows]
    return columns, materialized_rows


def check_database_connection(database_path: Path) -> bool:
    try:
        with get_connection(database_path) as connection:
            connection.execute("SELECT 1;").fetchone()
        return True
    except sqlite3.Error:
        return False
