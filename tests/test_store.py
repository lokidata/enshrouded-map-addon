import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from addon.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(str(tmp_path / "a.db"))


def test_grant_overwrites_level(store: Store) -> None:
    store.grant("1:t", "alice", "read", "admin")
    store.grant("1:t", "alice", "action", "admin")
    assert store.level_of("1:t") == "action"
    rows = store.list_access()
    assert len(rows) == 1 and rows[0].username == "alice" and rows[0].by == "admin"


def test_level_of_unknown_and_revoke(store: Store) -> None:
    assert store.level_of("9:x") is None
    store.grant("1:t", "alice", "read", "admin")
    store.revoke("1:t")
    assert store.level_of("1:t") is None


def test_prune_missing_removes_only_absent(store: Store) -> None:
    store.grant("1:t", "a", "read", "admin")
    store.grant("2:t", "b", "read", "admin")
    assert store.prune_missing({"1:t"}) == ["2:t"]
    assert [r.user_key for r in store.list_access()] == ["1:t"]


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
