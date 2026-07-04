"""SQLite connection management and schema bootstrap.

A single :class:`Database` instance owns one shared connection guarded by a
lock. Because the bot runs on an asyncio event loop, blocking DB calls in
handlers should be dispatched via :func:`asyncio.to_thread` so the loop is
never stalled. The internal lock makes the connection safe to use from those
worker threads.
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from utils.logging_config import get_logger

logger = get_logger(__name__)

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class DatabaseError(RuntimeError):
    """Raised for unrecoverable database problems."""


class Database:
    """Thin wrapper around a shared, thread-safe SQLite connection."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.RLock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            db_path, check_same_thread=False, isolation_level=None
        )
        self._conn.row_factory = sqlite3.Row
        # WAL improves concurrency between the writer and readers.
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        logger.info("Opened SQLite database at %s", db_path)

    def initialize(self) -> None:
        """Create tables/indexes if they do not already exist."""
        try:
            schema = _SCHEMA_PATH.read_text(encoding="utf-8")
        except OSError as exc:  # pragma: no cover - defensive
            raise DatabaseError(f"Could not read schema file: {exc}") from exc
        with self._lock:
            self._conn.executescript(schema)
        logger.info("Database schema initialized")

    @contextmanager
    def cursor(self) -> Iterator[sqlite3.Cursor]:
        """Yield a cursor within the shared lock, committing on success."""
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
                self._conn.commit()
            except sqlite3.Error:
                self._conn.rollback()
                raise
            finally:
                cur.close()

    def close(self) -> None:
        """Close the underlying connection."""
        with self._lock:
            self._conn.close()
        logger.info("Database connection closed")
