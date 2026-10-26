"""Database connections for the shop API."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

HW_DIR = Path(__file__).resolve().parent.parent
# CC_DB_PATH lets the tests point the API at a throwaway copy of the database.
DB_PATH = Path(os.getenv("CC_DB_PATH", HW_DIR / "data" / "data" / "campus_customs.db"))


def connect(read_only: bool) -> sqlite3.Connection:
    # FastAPI may open a connection in one worker thread and use it in another, so allow
    # that; each request gets its own connection and never shares it.
    mode = "ro" if read_only else "rw"
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode={mode}", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    """Read-only connection for catalogue and stock requests."""
    conn = connect(read_only=True)
    try:
        yield conn
    finally:
        conn.close()


def get_db_rw() -> Iterator[sqlite3.Connection]:
    """Read-write connection for accounts and sessions."""
    conn = connect(read_only=False)
    try:
        yield conn
    finally:
        conn.close()
