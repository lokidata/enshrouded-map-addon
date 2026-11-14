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

from addon import api, chestsort
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
        self.files: dict[str, str] = {}  # Pelican file store: path -> text
        self.file_ops: list[tuple[str, str]] = []  # ("read"|"write"|"list", path)
        # (op, path) -> one answer per call, in order: a status, or None to serve normally
        self.fail: dict[tuple[str, str], list[int | None]] = {}
        self.mangle: set[str] = set()  # next write to that path stores something else

    async def handle(self, request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(self.delay)  # lets concurrent requests interleave
        return self.respond(request)

    def respond(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "panel.example.test":
            self.pelican_calls += 1
            path = request.url.path
            if "/files/" in path:
                return self.file_op(request)
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

    def file_op(self, request: httpx.Request) -> httpx.Response:
        op = request.url.path.rsplit("/", 1)[1]
        op = {"contents": "read", "write": "write", "list": "list"}[op]
        target = request.url.params.get("file") or request.url.params["directory"]
        self.file_ops.append((op, target))
        queue = self.fail.get((op, target)) or [None]
        if (code := queue.pop(0)) is not None:
            return httpx.Response(code)
        if op == "write":
            text = request.content.decode()
            if target in self.mangle:
                self.mangle.discard(target)
                text += "corrupted"
            self.files[target] = text
            return httpx.Response(204)
        if op == "list":
            names = [
                {"attributes": {"name": f.rsplit("/", 1)[1], "is_file": True}}
                for f in self.files
                if f.rsplit("/", 1)[0] + "/" == target
            ]
            return httpx.Response(200, json={"data": names})
        if target not in self.files:
            return httpx.Response(404)
        return httpx.Response(200, text=self.files[target])

    def writes(self) -> list[str]:
        return [p for op, p in self.file_ops if op == "write"]


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
        backup_ignored="/*\n!/savegame/\n!/savegame/**",
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
    assert me.json() == {
        "username": "alice",
        "is_admin": False,
        "level": None,
        "backup_filtered": True,
        "chestsort": False,
    }
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
    assert me == {
        "username": "root",
        "is_admin": True,
        "level": "action",
        "backup_filtered": True,
        "chestsort": False,
    }
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
    keep = ("power", "backup", "chestsort")
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


@pytest.fixture
def client_full(fake: Fake, tmp_path: Path) -> Iterator[TestClient]:
    """Same app, no BACKUP_IGNORED: a backup would contain every file of the server."""
    settings = Settings(
        pelican_url="https://panel.example.test",
        pelican_api_key=KEY,  # type: ignore[arg-type]
        pelican_server_id="abcd1234",
        site_url="http://site.example.test",
        db_path=str(tmp_path / "addon.db"),
        allowed_origin="https://site.example.test",
    )
    with TestClient(create_app(settings, httpx.MockTransport(fake.handle))) as c:
        yield c


@pytest.mark.parametrize(
    "extra", [{}, {"confirm_full": False}, {"confirm_full": "true"}, {"confirm_full": 1}]
)
def test_unfiltered_backup_needs_confirm_full(
    client_full: TestClient, fake: Fake, extra: dict[str, Any]
) -> None:
    resp = post(client_full, "/backups", json=extra)
    assert (resp.status_code, resp.json()) == (422, {"detail": "full_backup_confirmation_required"})
    assert fake.backups_created == 0
    assert actions(client_full) == [
        ("root", "backup", "create", "full_backup_confirmation_required", None)
    ]


def test_unfiltered_backup_with_confirm_full_true_goes_through(
    client_full: TestClient, fake: Fake
) -> None:
    assert post(client_full, "/backups", json={"confirm_full": True}).status_code == 200
    assert fake.backups_created == 1


def test_filtered_backup_needs_no_confirmation(client: TestClient, fake: Fake) -> None:
    assert post(client, "/backups").status_code == 200
    assert fake.backups_created == 1


def test_me_tells_whether_backups_are_filtered(client: TestClient, client_full: TestClient) -> None:
    assert client.get("/addon/api/me", headers=as_("admin")).json()["backup_filtered"] is True
    assert client_full.get("/addon/api/me", headers=as_("admin")).json()["backup_filtered"] is False


# --- chestsort categories editor ---------------------------------------------------------------

CS = "/chestsort_categories.json"
SECRET_WORD = "zzmarqueurzz"  # content marker: must never reach the journal or the logs
CS_OBJ: dict[str, Any] = {
    "_readme": ["Ne pas utiliser « Nourriture »."],
    "categories": {
        "Minerais": {"words": ["minerai", SECRET_WORD], "items": ["Ore_Copper"]},
        "Bois": {"words": ["bois"], "items": ["Wood_Log", "Wood_*"]},
    },
}
CS_TEXT = chestsort.dump(CS_OBJ)
NEW_CATS = {**CS_OBJ["categories"], "Bois": {"words": ["bûche"], "items": ["Wood_Log"]}}


@pytest.fixture
def cs(fake: Fake, tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        pelican_url="https://panel.example.test",
        pelican_api_key=KEY,  # type: ignore[arg-type]
        pelican_server_id="abcd1234",
        site_url="http://site.example.test",
        db_path=str(tmp_path / "addon.db"),
        allowed_origin="https://site.example.test",
        backup_ignored="/x",
        chestsort_file=CS,
    )
    fake.files[CS] = CS_TEXT
    with TestClient(create_app(settings, httpx.MockTransport(fake.handle))) as c:
        yield c


def save(client: TestClient, who: str = "admin", **over: Any) -> httpx.Response:
    body = {"categories": NEW_CATS, "base_hash": chestsort.sha256(CS_TEXT), "confirm": True}
    resp: httpx.Response = client.put(
        "/addon/api/chestsort", headers=as_(who, WRITE), json={**body, **over}
    )
    return resp


def restore(client: TestClient, name: str, who: str = "admin", **over: Any) -> httpx.Response:
    body = {"name": name, "base_hash": chestsort.sha256(CS_TEXT), "confirm": True, **over}
    return post(client, "/chestsort/restore", who, json=body)


def bak(fake: Fake) -> str:
    return next(p for p in fake.files if p.startswith(CS + ".bak-"))


def test_chestsort_off_by_default_is_404(client: TestClient, fake: Fake) -> None:
    assert client.get("/addon/api/me", headers=as_("admin")).json()["chestsort"] is False
    assert client.get("/addon/api/chestsort", headers=as_("admin")).status_code == 404
    assert client.get("/addon/api/chestsort/backups", headers=as_("admin")).status_code == 404
    assert post(client, "/chestsort/preview", json={"categories": {}}).status_code == 404
    assert post(client, "/chestsort/restore", json={}).status_code == 404
    assert client.put("/addon/api/chestsort", headers=as_("admin", WRITE)).status_code == 404
    assert fake.file_ops == [] and actions(client) == []


def test_me_tells_chestsort_is_on(cs: TestClient) -> None:
    assert cs.get("/addon/api/me", headers=as_("admin")).json()["chestsort"] is True


def test_reader_sees_the_file(cs: TestClient, fake: Fake) -> None:
    grant(cs, ALICE_KEY, "read")
    resp = cs.get("/addon/api/chestsort", headers=as_("alice"))
    assert resp.json() == {
        "categories": CS_OBJ["categories"],
        "other_keys_kept": False,
        "hash": chestsort.sha256(CS_TEXT),
        "bytes": len(CS_TEXT.encode()),
    }
    fake.files[CS] = chestsort.dump({**CS_OBJ, "version": 2})
    assert cs.get("/addon/api/chestsort", headers=as_("alice")).json()["other_keys_kept"] is True


def test_file_over_1_mb_is_413(cs: TestClient, fake: Fake) -> None:
    fake.files[CS] = chestsort.dump({"categories": {"A": {"words": ["x" * 1_000_000]}}})
    resp = cs.get("/addon/api/chestsort", headers=as_("admin"))
    assert (resp.status_code, resp.json()) == (413, {"detail": "too_large"})


def test_unreadable_file_is_502(cs: TestClient, fake: Fake) -> None:
    fake.files[CS] = "{not json"
    resp = cs.get("/addon/api/chestsort", headers=as_("admin"))
    assert (resp.status_code, resp.json()) == (502, {"detail": "file_invalid"})
    del fake.files[CS]
    resp = cs.get("/addon/api/chestsort", headers=as_("admin"))
    assert (resp.status_code, resp.json()) == (502, {"detail": "pelican_not_found"})


def test_read_and_unlisted_users_cannot_write_chestsort(cs: TestClient, fake: Fake) -> None:
    grant(cs, ALICE_KEY, "read")
    for who in ("alice", "bob"):
        assert save(cs, who).status_code == 403
        assert post(cs, "/chestsort/preview", who, json={"categories": NEW_CATS}).status_code == 403
        assert restore(cs, "x", who).status_code == 403
    assert cs.get("/addon/api/chestsort", headers=as_("bob")).status_code == 403
    assert cs.get("/addon/api/chestsort/backups", headers=as_("bob")).status_code == 403
    assert fake.file_ops == [] and actions(cs) == []


def test_preview_shows_diff_and_writes_nothing(cs: TestClient, fake: Fake) -> None:
    grant(cs, ALICE_KEY, "action")
    resp = post(cs, "/chestsort/preview", "alice", json={"categories": NEW_CATS})
    body = resp.json()
    assert (body["errors"], body["changed"]) == ([], True)
    assert '+        "bûche"' in body["diff"] and '-        "bois"' in body["diff"]
    same = post(cs, "/chestsort/preview", json={"categories": CS_OBJ["categories"]}).json()
    assert (same["changed"], same["diff"]) == (False, [])
    assert fake.writes() == [] and actions(cs) == []  # a preview is not journalled


def test_preview_reports_errors_and_warnings(cs: TestClient) -> None:
    cats = {"Nourriture": {"words": ["bois"], "items": []}, "Bois": {"words": "bois", "items": []}}
    body = post(cs, "/chestsort/preview", json={"categories": cats}).json()
    assert any("« words » doit être une liste" in e for e in body["errors"])
    assert any("groupe intégré" in w for w in body["warnings"])


def test_save_writes_backup_then_file(cs: TestClient, fake: Fake) -> None:
    resp = save(cs)
    new_text = chestsort.dump({**CS_OBJ, "categories": NEW_CATS})
    assert resp.status_code == 200
    name = resp.json()["backup"]
    assert chestsort.is_bak_name("chestsort_categories.json", name)
    assert resp.json()["hash"] == chestsort.sha256(new_text)
    assert fake.writes() == ["/" + name, CS]
    assert fake.file_ops == [
        ("read", CS),
        ("write", "/" + name),
        ("read", "/" + name),
        ("write", CS),
        ("read", CS),
    ]
    assert fake.files == {CS: new_text, "/" + name: CS_TEXT}  # _readme kept
    assert actions(cs) == [("root", "chestsort", "save", "ok", None)]


@pytest.mark.parametrize("extra", [{"confirm": False}, {"confirm": "true"}, {"confirm": 1}])
def test_save_needs_confirm_true(cs: TestClient, fake: Fake, extra: dict[str, Any]) -> None:
    resp = save(cs, **extra)
    assert (resp.status_code, resp.json()) == (422, {"detail": "confirmation_required"})
    resp = cs.put(
        "/addon/api/chestsort",
        headers=as_("admin", WRITE),
        json={"categories": NEW_CATS, "base_hash": "x"},
    )
    assert resp.status_code == 422
    assert fake.file_ops == []
    assert [a[3] for a in actions(cs)] == ["confirmation_required"] * 2


@pytest.mark.parametrize("body", ["not json", "[]", '{"categories": {}}'])
def test_malformed_save_is_422_journalled(cs: TestClient, fake: Fake, body: str) -> None:
    resp = cs.put("/addon/api/chestsort", headers=as_("admin", WRITE), content=body)
    assert (resp.status_code, resp.json()) == (422, {"detail": "invalid_request"})
    assert fake.file_ops == []
    assert actions(cs) == [("root", "chestsort", "save", "invalid_request", None)]


def test_file_changed_elsewhere_writes_nothing(cs: TestClient, fake: Fake) -> None:
    fake.files[CS] = CS_TEXT + " "  # edited in the panel since the view
    resp = save(cs)
    assert (resp.status_code, resp.json()) == (409, {"detail": "changed_elsewhere"})
    assert fake.writes() == []
    assert actions(cs) == [("root", "chestsort", "save", "changed_elsewhere", None)]


@pytest.mark.parametrize(
    ("cats", "message"),
    [
        (["Bois"], "« categories » doit être un objet"),
        ({"Bois": {"words": [], "items": [], "color": "red"}}, "clé inconnue « color »"),
        ({"Bois": {"words": "bois", "items": []}}, "« words » doit être une liste"),
        ({"Bois": {"words": [], "items": ["x" * 200_000]}}, "« items » ne doit contenir"),
        ({}, "de 1 à 200 catégories"),
    ],
)
def test_invalid_categories_refused_with_messages(
    cs: TestClient, fake: Fake, cats: Any, message: str
) -> None:
    resp = save(cs, categories=cats)
    assert resp.status_code == 422
    assert resp.json()["detail"] == "invalid_content"
    assert any(message in e for e in resp.json()["errors"])
    assert fake.writes() == []
    assert actions(cs) == [("root", "chestsort", "save", "invalid_content", None)]


def test_body_over_1_mb_is_413_before_anything(cs: TestClient, fake: Fake) -> None:
    big: dict[str, Any] = {"categories": {"A": {"words": ["x" * 1_100_000], "items": []}}}
    resp = save(cs, **big)
    assert (resp.status_code, resp.json()) == (413, {"detail": "too_large"})
    resp = post(cs, "/chestsort/preview", json=big)
    assert (resp.status_code, resp.json()) == (413, {"detail": "too_large"})
    assert fake.file_ops == []
    assert actions(cs) == [("root", "chestsort", "save", "too_large", None)]


def test_backup_write_failing_never_writes_the_file(cs: TestClient, fake: Fake) -> None:
    orig = fake.file_op

    def failing(request: httpx.Request) -> httpx.Response:
        if ".bak-" in request.url.params.get("file", "") and request.method == "POST":
            fake.file_ops.append(("write", request.url.params["file"]))
            return httpx.Response(500)
        return orig(request)

    fake.file_op = failing  # type: ignore[method-assign]
    resp = save(cs)
    assert (resp.status_code, resp.json()) == (502, {"detail": "pelican_unavailable"})
    assert CS not in fake.writes() and fake.files[CS] == CS_TEXT
    assert actions(cs) == [("root", "chestsort", "save", "pelican_unavailable", None)]


def test_backup_read_back_differing_never_writes_the_file(cs: TestClient, fake: Fake) -> None:
    orig = fake.file_op

    def mangle_bak(request: httpx.Request) -> httpx.Response:
        if ".bak-" in request.url.params.get("file", ""):
            fake.mangle.add(request.url.params["file"])
        return orig(request)

    fake.file_op = mangle_bak  # type: ignore[method-assign]
    resp = save(cs)
    assert (resp.status_code, resp.json()) == (502, {"detail": "backup_failed"})
    assert CS not in fake.writes() and fake.files[CS] == CS_TEXT
    assert actions(cs) == [("root", "chestsort", "save", "backup_failed", None)]


def test_read_back_mismatch_rolls_back(cs: TestClient, fake: Fake) -> None:
    fake.mangle.add(CS)
    resp = save(cs)
    assert (resp.status_code, resp.json()) == (502, {"detail": "verify_failed"})
    assert fake.writes() == ["/" + bak(fake)[1:], CS, CS]
    assert fake.files[CS] == CS_TEXT
    assert actions(cs) == [("root", "chestsort", "save", "rolled_back", None)]
    assert save(cs).status_code == 429  # the file was written: the window started


def test_read_back_failing_rolls_back(cs: TestClient, fake: Fake) -> None:
    fake.fail[("read", CS)] = [None, 500]
    resp = save(cs)
    assert (resp.status_code, resp.json()) == (502, {"detail": "verify_failed"})
    assert fake.writes()[1:] == [CS, CS] and fake.files[CS] == CS_TEXT
    assert [a[3] for a in actions(cs)] == ["rolled_back"]


def test_rollback_failing_is_journalled(cs: TestClient, fake: Fake) -> None:
    fake.mangle.add(CS)
    fake.fail[("write", CS)] = [None, 500]
    resp = save(cs)
    assert (resp.status_code, resp.json()) == (502, {"detail": "verify_failed"})
    assert [a[3] for a in actions(cs)] == ["rollback_failed"]


@pytest.mark.parametrize(
    ("code", "detail", "journal", "window"),
    [
        (500, "verify_failed", "rolled_back", True),  # may be half written: roll back
        (403, "pelican_denied", "pelican_denied", False),  # refused: nothing written
    ],
)
def test_file_write_failing(
    cs: TestClient, fake: Fake, code: int, detail: str, journal: str, window: bool
) -> None:
    fake.fail[("write", CS)] = [code]
    resp = save(cs)
    assert (resp.status_code, resp.json()) == (502, {"detail": detail})
    assert fake.files[CS] == CS_TEXT
    assert [a[3] for a in actions(cs)] == [journal]
    assert save(cs).status_code == (429 if window else 200)


def test_chestsort_writes_are_rate_limited_for_10_s(cs: TestClient, fake: Fake) -> None:
    now = [100.0]
    cs.app.state.throttle = Throttle(lambda: now[0])  # type: ignore[attr-defined]
    assert save(cs, base_hash="stale").status_code == 409  # a refusal starts no window
    assert save(cs).status_code == 200
    new_hash = chestsort.sha256(fake.files[CS])
    now[0] += 9.5
    resp = save(cs, base_hash=new_hash, categories=CS_OBJ["categories"])
    assert (resp.status_code, resp.headers["Retry-After"]) == (429, "1")
    assert restore(cs, bak(fake)[1:], base_hash=new_hash).status_code == 429  # shared key
    now[0] += 0.5
    assert save(cs, base_hash=new_hash, categories=CS_OBJ["categories"]).status_code == 200
    assert [a[3] for a in actions(cs)] == [
        "changed_elsewhere",
        "ok",
        "rate_limited",
        "rate_limited",
        "ok",
    ]


def test_slow_panel_on_save_is_504_and_starts_the_window(
    cs: TestClient, fake: Fake, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(api, "ACTION_TIMEOUT", 0.05)
    fake.delay = 0.2
    resp = save(cs)
    assert (resp.status_code, resp.json()) == (504, {"detail": "pelican_timeout"})
    fake.delay = 0
    assert save(cs).status_code == 429
    assert [a[3] for a in actions(cs)] == ["timeout", "rate_limited"]


def test_two_concurrent_saves_make_one_write_sequence(cs: TestClient, fake: Fake) -> None:
    fake.delay = 0.05
    with ThreadPoolExecutor(2) as pool:
        codes = sorted(pool.map(lambda _: save(cs).status_code, range(2)))
    assert codes == [200, 429]
    assert len(fake.writes()) == 2 and fake.writes()[1] == CS


def test_backups_lists_the_20_newest_bak_files_only(cs: TestClient, fake: Fake) -> None:
    grant(cs, ALICE_KEY, "read")
    for day in range(1, 26):
        fake.files[f"{CS}.bak-202601{day:02d}-000000"] = "{}"
    fake.files["/other.json.bak-20260101-000000"] = "{}"
    fake.files[CS + ".bak-20260101-000000.json"] = "{}"
    names = cs.get("/addon/api/chestsort/backups", headers=as_("alice")).json()
    assert len(names) == 20
    assert names[0] == "chestsort_categories.json.bak-20260125-000000"
    assert names[-1] == "chestsort_categories.json.bak-20260106-000000"
    assert fake.file_ops == [("list", "/")]


def test_restore_from_a_listed_backup(cs: TestClient, fake: Fake) -> None:
    old = chestsort.dump({**CS_OBJ, "categories": NEW_CATS})
    fake.files[CS + ".bak-20260101-000000"] = old
    resp = restore(cs, "chestsort_categories.json.bak-20260101-000000")
    assert resp.status_code == 200
    fresh = "/" + resp.json()["backup"]
    assert fake.writes() == [fresh, CS]
    assert (fake.files[CS], fake.files[fresh]) == (old, CS_TEXT)
    assert actions(cs) == [("root", "chestsort", "restore", "ok", None)]


@pytest.mark.parametrize(
    ("name", "detail"),
    [
        ("../etc/passwd", "invalid_backup_name"),
        ("/chestsort_categories.json.bak-20260101-000000", "invalid_backup_name"),
        ("chestsort_categories.json.bak-20260101-000000/../x", "invalid_backup_name"),
        ("other.json.bak-20260101-000000", "invalid_backup_name"),
        ("chestsort_categories.json.bak-20260101-000000.json", "invalid_backup_name"),
        ("chestsort_categories.json", "invalid_backup_name"),
        ("chestsort_categories.json.bak-20260202-000000", "unknown_backup"),  # not listed
    ],
)
def test_restore_only_from_listed_bak_names(
    cs: TestClient, fake: Fake, name: str, detail: str
) -> None:
    fake.files[CS + ".bak-20260101-000000"] = CS_TEXT
    fake.files["/other.json.bak-20260101-000000"] = CS_TEXT
    resp = restore(cs, name)
    assert (resp.status_code, resp.json()["detail"]) == (
        (404 if detail == "unknown_backup" else 422),
        detail,
    )
    assert fake.writes() == [] and all(op != "read" for op, _ in fake.file_ops)
    assert [a[3] for a in actions(cs)] == [detail]


def test_restore_of_an_invalid_backup_is_refused(cs: TestClient, fake: Fake) -> None:
    fake.files[CS + ".bak-20260101-000000"] = '{"categories": []}'
    resp = restore(cs, "chestsort_categories.json.bak-20260101-000000")
    assert (resp.status_code, resp.json()["detail"]) == (422, "invalid_content")
    assert fake.writes() == []


def test_restore_needs_confirm_true(cs: TestClient, fake: Fake) -> None:
    fake.files[CS + ".bak-20260101-000000"] = CS_TEXT
    resp = restore(cs, "chestsort_categories.json.bak-20260101-000000", confirm="true")
    assert (resp.status_code, resp.json()) == (422, {"detail": "confirmation_required"})
    assert fake.file_ops == []


def test_contents_never_in_journal_or_logs(
    cs: TestClient, fake: Fake, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    cats = {**NEW_CATS, "Neuf": {"words": [SECRET_WORD + "2"], "items": ["Rare_" + SECRET_WORD]}}
    assert save(cs, categories=cats).status_code == 200
    fake.mangle.add(CS)
    cs.app.state.throttle = Throttle()  # type: ignore[attr-defined]
    save(cs, base_hash=chestsort.sha256(fake.files[CS]))
    save(cs, categories={"Bois": {"words": SECRET_WORD, "items": []}})
    journal = cs.get("/addon/api/journal", headers=as_("admin")).text
    assert SECRET_WORD not in journal
    logs = " ".join(r.getMessage() + str(r.args) for r in caplog.records)
    assert SECRET_WORD not in logs and KEY not in logs
    assert "categories=3 items=" in logs
