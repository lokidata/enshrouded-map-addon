import asyncio
import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from addon import api
from addon.api import create_app
from addon.config import Settings
from addon.throttle import Throttle

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
BACKUP = {
    "uuid": "u1",
    "name": "b1",
    "bytes": 10,
    "created_at": "2026-01-01T00:00:00+00:00",
    "completed_at": None,
    "is_successful": None,
    "is_locked": False,
}


class Fake:
    """Site + Pelican behind one MockTransport; tests mutate the fields."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {"admin": ADMIN, "alice": ALICE, "bob": BOB}
        self.users = [ALICE, BOB]  # the site's /auth/users never lists the administrator
        self.site_down = False
        self.pelican_status = 200
        self.pelican_calls = 0
        self.users_cookies: list[str | None] = []
        self.state = "running"
        self.power_status = 204
        self.signals: list[str] = []
        self.backup_status = 200
        self.backup_body: Any = {"attributes": BACKUP}
        self.backups_created = 0
        self.delay = 0.0

    async def handle(self, request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(self.delay)  # lets concurrent requests interleave
        return self.respond(request)

    def respond(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "panel.example.test":
            self.pelican_calls += 1
            path = request.url.path
            if path.endswith("/power"):
                self.signals.append(json.loads(request.content)["signal"])
                return httpx.Response(self.power_status)
            if path.endswith("/backups") and request.method == "POST":
                self.backups_created += 1
                return httpx.Response(self.backup_status, json=self.backup_body)
            if self.pelican_status != 200:
                return httpx.Response(self.pelican_status)
            if path.endswith("/backups"):
                return httpx.Response(200, json={"data": [{"attributes": BACKUP}]})
            stats = {"attributes": {**STATS["attributes"], "current_state": self.state}}
            return httpx.Response(200, json=stats if path.endswith("/resources") else INFO)
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


def post(client: TestClient, path: str, who: str = "admin", **kw: Any) -> httpx.Response:
    resp: httpx.Response = client.post(f"/addon/api{path}", headers=as_(who, WRITE), **kw)
    return resp


def actions(client: TestClient) -> list[tuple[Any, ...]]:
    rows = client.get("/addon/api/journal", headers=as_("admin")).json()
    keep = ("power", "backup")
    return [
        (r["username"], r["action"], r["target"], r["result"], r["pelican_status"])
        for r in reversed(rows)
        if r["action"] in keep
    ]


def test_read_and_unlisted_users_cannot_act(client: TestClient, fake: Fake) -> None:
    grant(client, ALICE_KEY, "read")
    for who in ("alice", "bob"):
        assert post(client, "/power", who, json={"signal": "start"}).status_code == 403
        assert post(client, "/backups", who).status_code == 403
    assert client.get("/addon/api/backups", headers=as_("bob")).status_code == 403
    assert actions(client) == [] and fake.pelican_calls == 0


def test_writes_need_the_csrf_header(client: TestClient, fake: Fake) -> None:
    headers = as_("admin", {"Origin": "https://site.example.test"})
    assert (
        client.post("/addon/api/power", json={"signal": "start"}, headers=headers).status_code
        == 403
    )
    assert client.post("/addon/api/backups", headers=headers).status_code == 403
    assert fake.pelican_calls == 0


@pytest.mark.parametrize(
    "kw",
    [{"json": {"signal": "kill"}}, {}, {"json": {}}, {"content": b"not json"}, {"json": ["stop"]}],
)
def test_invalid_power_request_is_422_journalled(
    client: TestClient, fake: Fake, kw: dict[str, Any]
) -> None:
    resp = post(client, "/power", **kw)
    assert resp.status_code == 422
    assert resp.json() == {"detail": "invalid_request"}
    target = "kill" if kw.get("json") == {"signal": "kill"} else "invalid"
    assert actions(client) == [("root", "power", target, "invalid_request", None)]
    assert fake.pelican_calls == 0


def test_power_target_never_journals_raw_input(client: TestClient) -> None:
    post(client, "/power", json={"signal": "<b>x</b>" * 50})
    assert actions(client)[0][2] == "invalid"


@pytest.mark.parametrize("signal", ["stop", "restart"])
@pytest.mark.parametrize("extra", [{}, {"confirm": False}, {"confirm": "true"}, {"confirm": 1}])
def test_stop_and_restart_need_confirm_true(
    client: TestClient, fake: Fake, signal: str, extra: dict[str, Any]
) -> None:
    resp = post(client, "/power", json={"signal": signal, **extra})
    assert (resp.status_code, resp.json()) == (422, {"detail": "confirmation_required"})
    assert actions(client) == [("root", "power", signal, "confirmation_required", None)]
    assert fake.pelican_calls == 0


@pytest.mark.parametrize(
    ("state", "signal"),
    [
        ("running", "start"),
        ("offline", "stop"),
        ("offline", "restart"),
        *[
            (s, sig)
            for s in ("starting", "stopping", "weird")
            for sig in ("start", "stop", "restart")
        ],
    ],
)
def test_wrong_state_is_409_and_nothing_sent(
    client: TestClient, fake: Fake, state: str, signal: str
) -> None:
    fake.state = state
    resp = post(client, "/power", json={"signal": signal, "confirm": True})
    assert (resp.status_code, resp.json()) == (409, {"detail": "wrong_state"})
    assert fake.signals == []
    assert actions(client) == [("root", "power", signal, "wrong_state", None)]


@pytest.mark.parametrize("power_status", [200, 204])
def test_power_ok_for_action_user(client: TestClient, fake: Fake, power_status: int) -> None:
    grant(client, ALICE_KEY, "action")
    fake.power_status = power_status
    resp = post(client, "/power", "alice", json={"signal": "stop", "confirm": True})
    assert (resp.status_code, resp.json()) == (200, {"signal": "stop", "result": "ok"})
    assert fake.signals == ["stop"]
    assert actions(client) == [("alice", "power", "stop", "ok", None)]


def test_start_when_offline_needs_no_confirm(client: TestClient, fake: Fake) -> None:
    fake.state = "offline"
    assert post(client, "/power", json={"signal": "start"}).status_code == 200
    assert fake.signals == ["start"]


def test_power_is_rate_limited_globally_for_30_s(client: TestClient, fake: Fake) -> None:
    now = [100.0]
    client.app.state.throttle = Throttle(lambda: now[0])  # type: ignore[attr-defined]
    grant(client, ALICE_KEY, "action")
    assert post(client, "/power", json={"signal": "restart", "confirm": True}).status_code == 200
    now[0] += 29.5
    resp = post(client, "/power", "alice", json={"signal": "stop", "confirm": True})
    assert resp.status_code == 429
    assert resp.headers["Retry-After"] == "1"
    assert resp.json() == {"detail": "rate_limited", "retry_after": 1}
    now[0] += 0.5
    assert (
        post(client, "/power", "alice", json={"signal": "stop", "confirm": True}).status_code == 200
    )
    assert fake.signals == ["restart", "stop"]
    assert [a[3] for a in actions(client)] == ["ok", "rate_limited", "ok"]


@pytest.mark.parametrize(
    ("code", "detail", "pstatus"),
    [(403, "pelican_denied", 403), (404, "pelican_not_found", 404)],
)
def test_refused_power_is_502_and_does_not_start_the_window(
    client: TestClient, fake: Fake, code: int, detail: str, pstatus: int | None
) -> None:
    fake.power_status = code
    resp = post(client, "/power", json={"signal": "stop", "confirm": True})
    assert (resp.status_code, resp.json()) == (502, {"detail": detail})
    fake.power_status = 204
    assert post(client, "/power", json={"signal": "stop", "confirm": True}).status_code == 200
    assert actions(client) == [
        ("root", "power", "stop", detail, pstatus),
        ("root", "power", "stop", "ok", None),
    ]


@pytest.mark.parametrize("path", ["/power", "/backups"])
def test_unavailable_write_may_have_applied_and_starts_the_window(
    client: TestClient, fake: Fake, path: str
) -> None:
    fake.power_status = fake.backup_status = 500
    body = {"signal": "stop", "confirm": True}
    resp = post(client, path, json=body)
    assert (resp.status_code, resp.json()) == (502, {"detail": "pelican_unavailable"})
    fake.power_status, fake.backup_status = 204, 200
    assert post(client, path, json=body).status_code == 429
    target = "stop" if path == "/power" else "create"
    assert [a[2:] for a in actions(client)] == [
        (target, "pelican_unavailable", None),
        (target, "rate_limited", None),
    ]


@pytest.mark.parametrize("code", [400, 409, 422])
def test_get_refusal_codes_are_502_unavailable(client: TestClient, fake: Fake, code: int) -> None:
    fake.pelican_status = code
    for path in ("/status", "/backups"):
        resp = client.get(f"/addon/api{path}", headers=as_("admin"))
        assert (resp.status_code, resp.json()) == (502, {"detail": "pelican_unavailable"})
    resp = post(client, "/power", json={"signal": "stop", "confirm": True})
    assert (resp.status_code, resp.json()) == (502, {"detail": "pelican_unavailable"})
    assert fake.signals == []
    assert actions(client) == [("root", "power", "stop", "pelican_unavailable", None)]


@pytest.mark.parametrize("path", ["/power", "/backups"])
def test_unexpected_error_is_journalled_and_500(
    client: TestClient, fake: Fake, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_: Any) -> None:
        raise RuntimeError("bug")

    pelican = client.app.state.pelican  # type: ignore[attr-defined]
    monkeypatch.setattr(pelican, "power", boom)
    monkeypatch.setattr(pelican, "create_backup", boom)
    resp = post(client, path, json={"signal": "stop", "confirm": True})
    assert (resp.status_code, resp.json()) == (500, {"detail": "internal_error"})
    assert [a[3] for a in actions(client)] == ["internal_error"]


@pytest.mark.parametrize("path", ["/power", "/backups"])
def test_second_request_waiting_too_long_for_the_lock_is_busy(
    client: TestClient, fake: Fake, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "LOCK_WAIT", 0.01)
    fake.delay = 0.2

    def send(_: int) -> int:
        return post(client, path, json={"signal": "stop", "confirm": True}).status_code

    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(send, range(2)))
    assert codes == [200, 409]
    assert sorted(a[3] for a in actions(client)) == ["busy", "ok"]


@pytest.mark.parametrize("path", ["/power", "/backups"])
def test_slow_panel_is_504_and_starts_the_window(
    client: TestClient, fake: Fake, path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "ACTION_TIMEOUT", 0.05)
    fake.delay = 0.2
    body = {"signal": "stop", "confirm": True}
    resp = post(client, path, json=body)
    assert (resp.status_code, resp.json()) == (504, {"detail": "pelican_timeout"})
    fake.delay = 0
    assert post(client, path, json=body).status_code == 429  # the lock was released
    assert [a[3] for a in actions(client)] == ["timeout", "rate_limited"]


def test_status_failure_before_power_is_502_and_journalled(client: TestClient, fake: Fake) -> None:
    fake.pelican_status = 403
    resp = post(client, "/power", json={"signal": "stop", "confirm": True})
    assert (resp.status_code, resp.json()) == (502, {"detail": "pelican_denied"})
    assert fake.signals == []
    assert actions(client) == [("root", "power", "stop", "pelican_denied", 403)]


def test_power_rejected_is_409(client: TestClient, fake: Fake) -> None:
    fake.power_status = 409
    resp = post(client, "/power", json={"signal": "stop", "confirm": True})
    assert (resp.status_code, resp.json()) == (409, {"detail": "pelican_rejected"})
    assert actions(client) == [("root", "power", "stop", "pelican_rejected", 409)]


def test_two_concurrent_stops_send_one_power_call(client: TestClient, fake: Fake) -> None:
    fake.delay = 0.05

    def stop() -> int:
        return post(client, "/power", json={"signal": "stop", "confirm": True}).status_code

    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(lambda _: stop(), range(2)))
    assert codes == [200, 429]
    assert fake.signals == ["stop"]


def test_backups_list_for_readers(client: TestClient, fake: Fake) -> None:
    grant(client, ALICE_KEY, "read")
    resp = client.get("/addon/api/backups", headers=as_("alice"))
    assert (resp.status_code, resp.json()) == (200, [BACKUP])
    fake.pelican_status = 500
    resp = client.get("/addon/api/backups", headers=as_("alice"))
    assert (resp.status_code, resp.json()) == (502, {"detail": "pelican_unavailable"})
    assert actions(client) == []


def test_backup_create_ok_then_rate_limited_for_300_s(client: TestClient, fake: Fake) -> None:
    now = [100.0]
    client.app.state.throttle = Throttle(lambda: now[0])  # type: ignore[attr-defined]
    resp = post(client, "/backups")
    assert (resp.status_code, resp.json()) == (200, BACKUP)
    now[0] += 299.5
    resp = post(client, "/backups")
    assert (resp.status_code, resp.headers["Retry-After"]) == (429, "1")
    now[0] += 0.5
    assert post(client, "/backups").status_code == 200
    assert fake.backups_created == 2
    assert actions(client) == [
        ("root", "backup", "create", "ok", None),
        ("root", "backup", "create", "rate_limited", None),
        ("root", "backup", "create", "ok", None),
    ]


def test_backup_created_with_unparsable_body_is_ok_and_starts_the_window(
    client: TestClient, fake: Fake
) -> None:
    fake.backup_status, fake.backup_body = 201, {}
    resp = post(client, "/backups")
    assert (resp.status_code, resp.json()) == (200, {"backup": None})
    assert post(client, "/backups").status_code == 429
    assert fake.backups_created == 1
    assert [a[3] for a in actions(client)] == ["ok", "rate_limited"]


def test_backup_and_power_windows_are_independent(client: TestClient, fake: Fake) -> None:
    assert post(client, "/backups").status_code == 200
    assert post(client, "/power", json={"signal": "stop", "confirm": True}).status_code == 200


def test_backup_rejected_is_409_and_does_not_start_the_window(
    client: TestClient, fake: Fake
) -> None:
    fake.backup_status = 400
    resp = post(client, "/backups")
    assert (resp.status_code, resp.json()) == (409, {"detail": "pelican_rejected"})
    fake.backup_status = 201
    assert post(client, "/backups").status_code == 200
    assert actions(client) == [
        ("root", "backup", "create", "pelican_rejected", 400),
        ("root", "backup", "create", "ok", None),
    ]


def test_key_never_in_action_responses_or_logs(
    client: TestClient, fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    bodies = []
    for code in (204, 400, 403, 500):
        fake.power_status = fake.backup_status = code
        bodies.append(post(client, "/power", json={"signal": "stop", "confirm": True}).text)
        bodies.append(post(client, "/backups").text)
    bodies.append(client.get("/addon/api/backups", headers=as_("admin")).text)
    bodies.append(client.get("/addon/api/journal", headers=as_("admin")).text)
    assert all(KEY not in b for b in bodies)
    assert all(KEY not in r.getMessage() and KEY not in str(r.args) for r in caplog.records)


def test_refused_write_is_logged_without_the_received_origin(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    headers = as_("admin", {"X-Addon": "1", "Origin": "https://evil.example.test\nforged"})
    with caplog.at_level("WARNING", logger="addon.api"):
        assert client.post("/addon/api/backups", headers=headers).status_code == 403
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "origin_mismatch" in text and "evil.example.test" not in text
