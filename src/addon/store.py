"""SQLite store: access list and short-lived audit journal (stdlib only)."""

import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

Level = Literal["read", "action"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS access (
    user_key TEXT PRIMARY KEY, username TEXT NOT NULL, level TEXT NOT NULL,
    by TEXT NOT NULL, at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, username TEXT NOT NULL,
    action TEXT NOT NULL, target TEXT NOT NULL, result TEXT NOT NULL, pelican_status INTEGER);
"""


@dataclass(frozen=True)
class AccessRow:
    user_key: str
    username: str
    level: Level
    by: str
    at: str


@dataclass(frozen=True)
class JournalRow:
    id: int
    at: str
    username: str
    action: str
    target: str
    result: str
    pelican_status: int | None


class Store:
    def __init__(self, path: str, journal_days: int = 1) -> None:
        self._days = journal_days
        self._lock = threading.Lock()  # one connection shared by FastAPI worker threads
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(_SCHEMA)
        self.purge(datetime.now(UTC), journal_days)

    def grant(self, user_key: str, username: str, level: Level, by: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO access (user_key, username, level, by, at)"
                " VALUES (?, ?, ?, ?, ?)",
                (user_key, username, level, by, datetime.now(UTC).isoformat()),
            )

    def revoke(self, user_key: str) -> None:
        with self._lock:
            self._db.execute("DELETE FROM access WHERE user_key = ?", (user_key,))

    def level_of(self, user_key: str) -> Level | None:
        with self._lock:
            row = self._db.execute(
                "SELECT level FROM access WHERE user_key = ?", (user_key,)
            ).fetchone()
        return row[0] if row else None

    def list_access(self) -> list[AccessRow]:
        with self._lock:
            rows = self._db.execute(
                "SELECT user_key, username, level, by, at FROM access ORDER BY username"
            ).fetchall()
        return [AccessRow(*r) for r in rows]

    def prune_missing(self, present_keys: set[str]) -> list[str]:
        removed = [r.user_key for r in self.list_access() if r.user_key not in present_keys]
        for key in removed:
            self.revoke(key)
        return removed

    def log(
        self, username: str, action: str, target: str, result: str, status: int | None = None
    ) -> None:
        now = datetime.now(UTC)
        with self._lock:
            self._db.execute(
                "INSERT INTO audit (at, username, action, target, result, pelican_status)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (now.isoformat(), username, action, target, result, status),
            )
        self.purge(now, self._days)

    def journal(self) -> list[JournalRow]:
        with self._lock:
            rows = self._db.execute(
                "SELECT id, at, username, action, target, result, pelican_status"
                " FROM audit ORDER BY id DESC"
            ).fetchall()
        return [JournalRow(*r) for r in rows]

    def purge(self, now: datetime, days: int) -> int:
        cutoff = (now - timedelta(days=days)).isoformat()
        with self._lock:
            return self._db.execute("DELETE FROM audit WHERE at < ?", (cutoff,)).rowcount
