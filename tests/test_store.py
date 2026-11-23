import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from addon.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(str(tmp_path / "a.db"))


def test_access_table_is_left_dormant(store: Store, tmp_path: Path) -> None:
    with sqlite3.connect(str(tmp_path / "a.db")) as c:
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "access_v2" in tables
    assert not any(hasattr(store, n) for n in ("grant", "revoke", "level_of", "list_access"))


def test_log_and_purge(store: Store) -> None:
    store.log("alice", "status", "server", "ok", 200)
    now = datetime.now(UTC)
    assert store.purge(now + timedelta(hours=1), 1) == 0
    assert len(store.journal()) == 1
    assert store.purge(now + timedelta(hours=25), 1) == 1
    assert store.journal() == []


def test_log_purges_old_rows(tmp_path: Path) -> None:
    path = str(tmp_path / "a.db")
    s = Store(path)
    s.log("old", "status", "server", "ok")
    old = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    with sqlite3.connect(path) as c:
        c.execute("UPDATE audit SET at = ?", (old,))
    s.log("new", "status", "server", "ok")
    assert [r.username for r in s.journal()] == ["new"]


def test_journal_newest_first_and_no_secret_columns(store: Store, tmp_path: Path) -> None:
    store.log("a", "x", "t", "ok")
    store.log("b", "x", "t", "ok")
    assert [r.username for r in store.journal()] == ["b", "a"]
    with sqlite3.connect(str(tmp_path / "a.db")) as c:
        cols = {r[1] for r in c.execute("PRAGMA table_info(audit)")}
    assert cols == {"id", "at", "username", "action", "target", "result", "pelican_status"}


def test_journal_limit(store: Store) -> None:
    for i in range(5):
        store.log(f"u{i}", "x", "t", "ok")
    assert [r.username for r in store.journal(limit=2)] == ["u4", "u3"]
