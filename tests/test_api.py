import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from addon.api import create_app
from addon.config import Settings

KEY = "pacc_TEST"
ADMIN = {"id": 1, "username": "root", "is_admin": True, "created_at": "2026-01-01T00:00:00"}
ALICE = {"id": 7, "username": "alice", "is_admin": False, "created_at": "2026-01-02T03:04:05"}
BOB = {"id": 8, "username": "bob", "is_admin": False, "created_at": "2026-01-03T00:00:00"}
ALICE_KEY = "7:2026-01-02T03:04:05"
BOB_KEY = "8:2026-01-03T00:00:00"
INFO = {"attributes": {"name": "My server"}}
STATS = {
    "attributes": {
        "current_state": "running",
        "resources": {"cpu_absolute": 1.5, "memory_bytes": 2, "disk_bytes": 3, "uptime": 4},
    }
}
WRITE = {"X-Addon": "1", "Origin": "https://site.example.test"}


class Fake:
    """Site + Pelican behind one MockTransport; tests mutate the fields."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {"admin": ADMIN, "alice": ALICE, "bob": BOB}
        self.users = [ALICE, BOB]  # the site's /auth/users never lists the administrator
        self.site_down = False
        self.pelican_status = 200
        self.pelican_calls = 0
        self.users_cookies: list[str | None] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "panel.example.test":
            self.pelican_calls += 1
            if self.pelican_status != 200:
                return httpx.Response(self.pelican_status)
            return httpx.Response(200, json=STATS if request.url.path.endswith("s") else INFO)
        if self.site_down:
            return httpx.Response(500)
        cookie = request.headers.get("cookie", "")
        if request.url.path == "/api/v1/auth/users":
            self.users_cookies.append(cookie)
            return httpx.Response(
                200, json=[{k: u[k] for k in ("id", "username", "created_at")} for u in self.users]
            )
        user = self.sessions.get(cookie.removeprefix("session="))
        return httpx.Response(200, json=user or {"username": None, "is_admin": False})


@pytest.fixture
def fake() -> Fake:
    return Fake()


@pytest.fixture
def client(fake: Fake, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        pelican_url="https://panel.example.test",
        pelican_api_key=KEY,  # type: ignore[arg-type]
        pelican_server_id="abcd1234",
        site_url="http://site.example.test",
        db_path=str(tmp_path / "addon.db"),
        allowed_origin="https://site.example.test",
    )
    app = create_app(settings, httpx.MockTransport(fake.handle))
    with TestClient(app) as c:
        yield c


def as_(who: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    return {"Cookie": f"session={who}", **(extra or {})}


def grant(client: TestClient, key: str, level: str | None) -> httpx.Response:
    resp: httpx.Response = client.put(
        f"/addon/api/access/{key}", json={"level": level}, headers=as_("admin", WRITE)
    )
    return resp


def test_no_cookie_is_401(client: TestClient) -> None:
    for path in ("/me", "/status", "/journal", "/access"):
        assert client.get(f"/addon/api{path}").status_code == 401


def test_logged_out_cookie_is_401(client: TestClient) -> None:
    assert client.get("/addon/api/me", headers=as_("nobody")).status_code == 401


def test_unknown_user_has_no_level_and_no_status(client: TestClient, fake: Fake) -> None:
    me = client.get("/addon/api/me", headers=as_("alice"))
    assert me.json() == {"username": "alice", "is_admin": False, "level": None}
    assert client.get("/addon/api/status", headers=as_("alice")).status_code == 403
    assert client.get("/addon/api/journal", headers=as_("alice")).status_code == 403
    assert fake.pelican_calls == 0


def test_read_user_sees_status_but_cannot_manage(client: TestClient) -> None:
    assert grant(client, ALICE_KEY, "read").status_code == 200
    assert client.get("/addon/api/me", headers=as_("alice")).json()["level"] == "read"
    status = client.get("/addon/api/status", headers=as_("alice"))
    assert status.status_code == 200
    assert status.json() == {
        "name": "My server",
        "state": "running",
        "cpu": 1.5,
        "memory_bytes": 2,
        "disk_bytes": 3,
        "uptime_ms": 4,
    }
    put = client.put(
        f"/addon/api/access/{BOB_KEY}", json={"level": "read"}, headers=as_("alice", WRITE)
    )
    assert put.status_code == 403
    assert client.get("/addon/api/access", headers=as_("alice")).status_code == 403


def test_read_user_journal_has_only_public_fields(client: TestClient) -> None:
    grant(client, ALICE_KEY, "read")
    grant(client, BOB_KEY, "read")
    rows = client.get("/addon/api/journal", headers=as_("alice")).json()
    assert rows and all(set(r) == {"at", "username", "action", "target", "result"} for r in rows)


def test_admin_has_action_and_everything(client: TestClient) -> None:
    me = client.get("/addon/api/me", headers=as_("admin")).json()
    assert me == {"username": "root", "is_admin": True, "level": "action"}
    for path in ("/status", "/journal", "/access"):
        assert client.get(f"/addon/api{path}", headers=as_("admin")).status_code == 200


def test_access_lists_site_users_with_levels_and_relays_cookie(
    client: TestClient, fake: Fake
) -> None:
    grant(client, ALICE_KEY, "action")
    rows = client.get("/addon/api/access", headers=as_("admin")).json()
    assert rows == [
        {"user_key": ALICE_KEY, "username": "alice", "level": "action"},
        {"user_key": BOB_KEY, "username": "bob", "level": None},
    ]
    assert fake.users_cookies[-1] == "session=admin"


def test_null_level_revokes(client: TestClient) -> None:
    grant(client, ALICE_KEY, "read")
    assert grant(client, ALICE_KEY, None).status_code == 200
    assert client.get("/addon/api/me", headers=as_("alice")).json()["level"] is None


def test_write_without_x_addon_is_403(client: TestClient) -> None:
    put = client.put(
        f"/addon/api/access/{ALICE_KEY}",
        json={"level": "read"},
        headers=as_("admin", {"Origin": "https://site.example.test"}),
    )
    assert put.status_code == 403
    assert client.get("/addon/api/me", headers=as_("alice")).json()["level"] is None


def test_write_with_wrong_or_missing_origin_is_403(client: TestClient) -> None:
    for origin in ({"Origin": "https://evil.example.test"}, {}):
        put = client.put(
            f"/addon/api/access/{ALICE_KEY}",
            json={"level": "read"},
            headers=as_("admin", {"X-Addon": "1", **origin}),
        )
        assert put.status_code == 403


def test_site_down_is_503(client: TestClient, fake: Fake) -> None:
    fake.site_down = True
    assert client.get("/addon/api/me", headers=as_("admin")).status_code == 503
    assert client.get("/addon/api/status", headers=as_("admin")).status_code == 503
    assert fake.pelican_calls == 0


@pytest.mark.parametrize(
    ("status", "detail"),
    [(403, "pelican_denied"), (404, "pelican_not_found"), (500, "pelican_unavailable")],
)
def test_pelican_errors_are_502(client: TestClient, fake: Fake, status: int, detail: str) -> None:
    fake.pelican_status = status
    resp = client.get("/addon/api/status", headers=as_("admin"))
    assert resp.status_code == 502
    assert resp.json() == {"detail": detail}
    assert client.get("/addon/api/journal", headers=as_("admin")).json() == []


def test_status_polls_are_not_journalled_but_access_changes_are(client: TestClient) -> None:
    grant(client, ALICE_KEY, "read")
    client.get("/addon/api/status", headers=as_("admin"))
    rows = client.get("/addon/api/journal", headers=as_("admin")).json()
    assert [(r["username"], r["action"], r["target"], r["result"]) for r in rows] == [
        ("root", "access", "alice", "read"),
    ]


def test_journal_returns_at_most_500_newest(client: TestClient) -> None:
    store = client.app.state.store  # type: ignore[attr-defined]
    for i in range(505):
        store.log("root", "access", f"u{i}", "read")
    rows = client.get("/addon/api/journal", headers=as_("admin")).json()
    assert len(rows) == 500
    assert rows[0]["target"] == "u504"


def test_other_admin_missing_from_site_list_is_404(client: TestClient, fake: Fake) -> None:
    fake.sessions["admin2"] = {**ADMIN, "id": 2, "username": "root2"}
    key = "2:2026-01-01T00:00:00"
    assert grant(client, key, "read").status_code == 404
    assert client.get("/addon/api/me", headers=as_("admin2")).json()["level"] == "action"


def test_access_prunes_users_missing_from_site_and_journals(client: TestClient, fake: Fake) -> None:
    grant(client, ALICE_KEY, "read")
    fake.users = [BOB]
    rows = client.get("/addon/api/access", headers=as_("admin")).json()
    assert [r["username"] for r in rows] == ["bob"]
    fake.users = [ALICE, BOB]
    assert client.get("/addon/api/me", headers=as_("alice")).json()["level"] is None
    first = client.get("/addon/api/journal", headers=as_("admin")).json()[0]
    assert (first["action"], first["target"], first["result"]) == ("access", "alice", "removed")


def test_recreated_account_with_same_id_has_no_level(client: TestClient, fake: Fake) -> None:
    grant(client, ALICE_KEY, "read")
    fake.sessions["alice"] = {**ALICE, "created_at": "2026-05-05T00:00:00"}
    assert client.get("/addon/api/me", headers=as_("alice")).json()["level"] is None
    assert client.get("/addon/api/status", headers=as_("alice")).status_code == 403


def test_put_unknown_user_is_404(client: TestClient) -> None:
    assert grant(client, "99:2026-01-01T00:00:00", "read").status_code == 404
    assert grant(client, "7:2026-05-05T00:00:00", "read").status_code == 404


def test_admin_cannot_be_given_a_level(client: TestClient) -> None:
    assert grant(client, "1:2026-01-01T00:00:00", "read").status_code == 400
    assert grant(client, "1:2026-01-01T00:00:00", None).status_code == 400


def test_invalid_level_is_422(client: TestClient) -> None:
    assert grant(client, ALICE_KEY, "owner").status_code == 422


def test_docs_are_disabled(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_key_never_in_responses_or_logs(
    client: TestClient, fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    bodies = [grant(client, ALICE_KEY, "read").text]
    for status in (200, 403, 404, 500):
        fake.pelican_status = status
        bodies.append(client.get("/addon/api/status", headers=as_("admin")).text)
    for path in ("/me", "/journal", "/access"):
        bodies.append(client.get(f"/addon/api{path}", headers=as_("admin")).text)
    assert all(KEY not in b for b in bodies)
    assert all(KEY not in r.getMessage() and KEY not in str(r.args) for r in caplog.records)


def test_site_users_without_created_at_is_503(client: TestClient, fake: Fake) -> None:
    for created in (None, ""):
        fake.users = [{"id": 7, "username": "alice", "created_at": created}]
        assert client.get("/addon/api/access", headers=as_("admin")).status_code == 503
        assert grant(client, f"7:{created}", "read").status_code == 503
