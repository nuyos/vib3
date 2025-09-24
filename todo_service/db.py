from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional, Union

DATABASE_DEFAULT = "todo.db"

def _ensure_table_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(todos)")}
    if "due_date" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN due_date TEXT")
    if "completed_at" not in columns:
        conn.execute("ALTER TABLE todos ADD COLUMN completed_at TEXT")

_database: Union[str, Path] = DATABASE_DEFAULT
_connection: Optional[sqlite3.Connection] = None


def configure(database: Union[str, Path]) -> None:
    """Configure the SQLite database path used by the application."""
    global _database
    close_connection()
    _database = database


def get_connection() -> sqlite3.Connection:
    """Return a shared SQLite connection, creating it on first use."""
    global _connection
    if _connection is None:
        db_path = _database
        if isinstance(db_path, Path):
            db_path = str(db_path)
        _connection = sqlite3.connect(db_path, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
    return _connection


def close_connection() -> None:
    """Close the active connection if it exists."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def init_schema() -> None:
    """Create database tables if they do not already exist."""
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('teacher', 'student'))
        );

        CREATE TABLE IF NOT EXISTS todos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            completed INTEGER NOT NULL DEFAULT 0,
            owner_id INTEGER NOT NULL,
            assignee_id INTEGER,
            due_date TEXT,
            completed_at TEXT,
            FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(assignee_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )
    _ensure_table_columns(conn)
    conn.commit()
