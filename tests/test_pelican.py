import asyncio
import json
from typing import Any

import httpx
import pytest

from addon.config import Settings
from addon.pelican import (
    Backup,
    PelicanClient,
    PelicanDenied,
    PelicanNotFound,
    PelicanRejected,
    PelicanUnavailable,
    ServerStatus,
)

SETTINGS = Settings(
    pelican_url="https://panel.example.test",
    pelican_api_key="pacc_TEST",  # type: ignore[arg-type]
    pelican_server_id="abcd1234",
    site_url="http://site.example.test",
)
INFO = {"object": "server", "attributes": {"name": "My server"}}
STATS = {
    "object": "stats",
    "attributes": {
        "current_state": "running",
        "is_suspended": False,
        "resources": {
            "memory_bytes": 100,
            "cpu_absolute": 12.5,
            "disk_bytes": 200,
            "network_rx_bytes": 1,
            "network_tx_bytes": 2,
            "uptime": 3000,
        },
    },
}


def call(handler: Any) -> ServerStatus:
    async def run() -> ServerStatus:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await PelicanClient(SETTINGS, client).status()

    return asyncio.run(run())


def ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=STATS if request.url.path.endswith("/resources") else INFO)


def test_maps_status_and_sends_exact_requests() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return ok(request)

    assert call(handler) == ServerStatus("My server", "running", 12.5, 100, 200, 3000)
    assert sorted(str(r.url) for r in seen) == [
        "https://panel.example.test/api/client/servers/abcd1234",
        "https://panel.example.test/api/client/servers/abcd1234/resources",
    ]
    for r in seen:
        assert r.method == "GET"
        assert r.headers["Authorization"] == "Bearer pacc_TEST"
        assert r.headers["Accept"] == "application/json"


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (403, PelicanDenied),
        (404, PelicanNotFound),
        (500, PelicanUnavailable),
        (302, PelicanUnavailable),
    ],
)
def test_error_statuses(status: int, exc: type[Exception]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"Location": "https://evil.example.test/"})

    with pytest.raises(exc) as info:
        call(handler)
    assert "pacc_TEST" not in str(info.value) + repr(info.value)


def test_timeout_is_unavailable_without_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    with pytest.raises(PelicanUnavailable) as info:
        call(handler)
    assert "pacc_TEST" not in str(info.value) + repr(info.value) + repr(info.value.__cause__)


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        [],
        {},
        {"attributes": {}},
        {"attributes": {"current_state": "running", "resources": {}}},
        {"attributes": {"current_state": "running", "resources": {"memory_bytes": "x"}}},
    ],
)
def test_unexpected_shapes_are_unavailable(body: Any) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/resources"):
            return (
                httpx.Response(200, json=body)
                if body != "not json"
                else httpx.Response(200, content=b"not json")
            )
        return httpx.Response(200, json=INFO)

    with pytest.raises(PelicanUnavailable):
        call(handler)


def test_bad_info_shape_is_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/resources"):
            return httpx.Response(200, json=STATS)
        return httpx.Response(200, json={"attributes": {"name": 5}})

    with pytest.raises(PelicanUnavailable):
        call(handler)


@pytest.mark.parametrize(
    "stats_body",
    [
        '{"attributes":{"current_state":"running","resources":{"cpu_absolute":NaN,"memory_bytes":1,"disk_bytes":1,"uptime":1}}}',
        '{"attributes":{"current_state":"running","resources":{"cpu_absolute":1,"memory_bytes":Infinity,"disk_bytes":1,"uptime":1}}}',
        '{"attributes":{"current_state":"running","resources":{"cpu_absolute":1,"memory_bytes":1,"disk_bytes":-Infinity,"uptime":1}}}',
        '{"attributes":{"current_state":"running","resources":{"cpu_absolute":1,"memory_bytes":1,"disk_bytes":1,"uptime":"3"}}}',
        '{"attributes":{"current_state":"running","resources":{"cpu_absolute":1,"memory_bytes":-1,"disk_bytes":1,"uptime":1}}}',
        '{"attributes":{"current_state":"running","resources":{"cpu_absolute":-0.5,"memory_bytes":1,"disk_bytes":1,"uptime":1}}}',
    ],
)
def test_non_finite_or_bad_numbers_are_unavailable(stats_body: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/resources"):
            return httpx.Response(200, content=stats_body)
        return httpx.Response(200, json=INFO)

    with pytest.raises(PelicanUnavailable):
        call(handler)


def refuse(detail: str) -> Any:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"errors": [{"detail": detail}]})

    return handler


def test_failure_is_logged_with_reason_and_refused_ip_but_not_the_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    detail = "This IP address (172.22.0.1) does not have permission to access the API"
    with caplog.at_level("WARNING", logger="addon.pelican"), pytest.raises(PelicanDenied):
        call(refuse(detail))
    text = " ".join(r.getMessage() for r in caplog.records)
    assert "denied" in text and "403" in text and "172.22.0.1" in text
    assert "pacc_TEST" not in text


def test_unreachable_is_logged_with_the_error_type(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out", request=request)

    with caplog.at_level("WARNING", logger="addon.pelican"), pytest.raises(PelicanUnavailable):
        call(handler)
    assert "ConnectTimeout" in " ".join(r.getMessage() for r in caplog.records)


def test_detail_is_single_line_and_truncated(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING", logger="addon.pelican"), pytest.raises(PelicanDenied):
        call(refuse("line1\nline2\r" + "x" * 500))
    msg = caplog.records[0].getMessage()
    assert "\n" not in msg and "\r" not in msg and len(msg) < 400


def test_same_failure_is_logged_once_per_minute(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = [1000.0]
    monkeypatch.setattr("addon.pelican.time.monotonic", lambda: now[0])

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(refuse("a"))) as client:
            pelican = PelicanClient(SETTINGS, client)
            for _ in range(3):  # a 15 s poll from several viewers
                with pytest.raises(PelicanDenied):
                    await pelican.status()
            now[0] += 61
            with pytest.raises(PelicanDenied):
                await pelican.status()

    with caplog.at_level("WARNING", logger="addon.pelican"):
        asyncio.run(run())
    assert len(caplog.records) == 2


def test_bad_resources_shape_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = (
            {"attributes": {"current_state": "running"}}
            if "resources" in str(request.url)
            else INFO
        )
        return httpx.Response(200, json=body)

    with caplog.at_level("WARNING", logger="addon.pelican"), pytest.raises(PelicanUnavailable):
        call(handler)
    assert "bad_response" in caplog.records[0].getMessage()


BACKUP = {
    "uuid": "u1",
    "name": "b1",
    "bytes": 10,
    "created_at": "2026-01-01T00:00:00+00:00",
    "completed_at": "2026-01-01T00:01:00+00:00",
    "is_successful": True,
    "is_locked": False,
}
PENDING = {**BACKUP, "uuid": "u2", "completed_at": None, "is_successful": None}


def run_client(handler: Any, method: str, *args: Any) -> Any:
    async def run() -> Any:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await getattr(PelicanClient(SETTINGS, client), method)(*args)

    return asyncio.run(run())


@pytest.mark.parametrize("code", [200, 201, 202, 204])
def test_power_sends_exact_request(code: int) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(code)

    assert run_client(handler, "power", "restart") is None
    (r,) = seen
    assert (r.method, str(r.url)) == (
        "POST",
        "https://panel.example.test/api/client/servers/abcd1234/power",
    )
    assert r.content == b'{"signal":"restart"}'
    assert r.headers["Authorization"] == "Bearer pacc_TEST"


@pytest.mark.parametrize(
    ("status", "exc"),
    [
        (403, PelicanDenied),
        (404, PelicanNotFound),
        (400, PelicanRejected),
        (409, PelicanRejected),
        (422, PelicanRejected),
        (500, PelicanUnavailable),
        (302, PelicanUnavailable),
    ],
)
@pytest.mark.parametrize("method", ["power", "create_backup"])
def test_write_error_statuses(status: int, exc: type[Exception], method: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers={"Location": "https://evil.example.test/"})

    args = ("stop",) if method == "power" else ()
    with pytest.raises(exc) as info:
        run_client(handler, method, *args)
    assert "pacc_TEST" not in str(info.value) + repr(info.value)


def test_rejection_reason_goes_to_the_log_only(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"errors": [{"detail": "Backup limit reached"}]})

    with caplog.at_level("WARNING", logger="addon.pelican"), pytest.raises(PelicanRejected) as info:
        run_client(handler, "create_backup")
    assert "rejected" in caplog.text and "Backup limit reached" in caplog.text
    assert "Backup limit" not in str(info.value) and "pacc_TEST" not in caplog.text
    assert info.value.args == (400,)  # the route journals Pelican's status


def test_power_timeout_is_unavailable_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom", request=request)

    with caplog.at_level("WARNING", logger="addon.pelican"), pytest.raises(PelicanUnavailable):
        run_client(handler, "power", "start")
    assert "ConnectTimeout" in caplog.text and "pacc_TEST" not in caplog.text


def test_list_backups_parses_two() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert (request.method, request.url.path.endswith("/backups")) == ("GET", True)
        return httpx.Response(200, json={"data": [{"attributes": BACKUP}, {"attributes": PENDING}]})

    first, second = run_client(handler, "list_backups")
    assert first == Backup(
        "u1", "b1", 10, "2026-01-01T00:00:00+00:00", "2026-01-01T00:01:00+00:00", True, False
    )
    assert (second.completed_at, second.is_successful) == (None, None)


def test_create_backup_posts_empty_body_and_parses() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"attributes": PENDING})

    assert run_client(handler, "create_backup").uuid == "u2"
    assert (seen[0].method, seen[0].content) == ("POST", b"{}")


@pytest.mark.parametrize(
    "body",
    [
        [],
        {},
        {"data": {}},
        {"data": [{}]},
        {"data": [{"attributes": {**BACKUP, "bytes": "x"}}]},
        {"data": [{"attributes": {**BACKUP, "is_locked": "no"}}]},
        {"data": [{"attributes": {**BACKUP, "name": 5}}]},
        {"data": [{"attributes": {**BACKUP, "completed_at": 5}}]},
        {"data": [{"attributes": {**BACKUP, "is_successful": "yes"}}]},
    ],
)
def test_list_backups_bad_shapes_are_unavailable(body: Any) -> None:
    with pytest.raises(PelicanUnavailable):
        run_client(lambda request: httpx.Response(200, json=body), "list_backups")


@pytest.mark.parametrize("status", [400, 409, 422])
@pytest.mark.parametrize("method", ["status", "list_backups"])
def test_get_refusal_codes_are_unavailable(status: int, method: str) -> None:
    # PelicanRejected means "a write was refused": a GET never raises it
    with pytest.raises(PelicanUnavailable):
        run_client(lambda request: httpx.Response(status), method)


def test_create_backup_bad_shape_is_none_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    # Pelican already created the backup: a shape we cannot parse is still a success
    with caplog.at_level("WARNING", logger="addon.pelican"):
        result = run_client(
            lambda request: httpx.Response(200, json={"attributes": {}}), "create_backup"
        )
    assert result is None and "bad_response" in caplog.text


def test_create_backup_201_parses() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"attributes": PENDING})

    assert run_client(handler, "create_backup").uuid == "u2"


@pytest.mark.parametrize(("code", "body"), [(201, {}), (202, None), (204, None)])
def test_create_backup_2xx_without_body_is_none(code: int, body: Any) -> None:
    assert run_client(lambda request: httpx.Response(code, json=body), "create_backup") is None


def test_create_backup_2xx_invalid_json_is_none() -> None:
    assert (
        run_client(lambda request: httpx.Response(200, content=b"<html>"), "create_backup") is None
    )


def test_create_backup_sends_the_ignore_list_when_configured() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"attributes": PENDING})

    settings = SETTINGS.model_copy(update={"backup_ignored": "/*\n!/savegame/\n!/savegame/**"})

    async def run() -> Any:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await PelicanClient(settings, client).create_backup()

    asyncio.run(run())
    assert json.loads(seen[0].content) == {"ignored": "/*\n!/savegame/\n!/savegame/**"}


FILES = "/api/client/servers/abcd1234/files"
TEXT = '{"mot": "épée\\n"}\nligne 2\n'


def test_read_file_sends_exact_request_and_returns_text() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=TEXT.encode(), headers={"Content-Type": "text/plain"})

    assert run_client(handler, "read_file", "/a b/é.json") == TEXT
    req = seen[0]
    assert (req.method, req.url.path) == ("GET", FILES + "/contents")
    assert req.url.params["file"] == "/a b/é.json"
    assert "%20" in str(req.url) or "+" in str(req.url)  # encoded by httpx, not by hand
    assert req.headers["Authorization"] == "Bearer pacc_TEST"


def test_write_file_posts_raw_utf8_body_and_round_trips() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(204)

    assert run_client(handler, "write_file", "/dir/x.json", TEXT) is None
    req = seen[0]
    assert (req.method, req.url.path) == ("POST", FILES + "/write")
    assert req.url.params["file"] == "/dir/x.json"
    assert req.content.decode("utf-8") == TEXT
    assert req.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_list_files_returns_plain_file_names_only() -> None:
    seen: list[httpx.Request] = []
    body = {
        "object": "list",
        "data": [
            {"object": "file_object", "attributes": {"name": "a.json", "is_file": True}},
            {"object": "file_object", "attributes": {"name": "sub", "is_file": False}},
            {"object": "file_object", "attributes": {"name": "b.bak", "is_file": True}},
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=body)

    assert run_client(handler, "list_files", "/dir") == ["a.json", "b.bak"]
    assert (seen[0].method, seen[0].url.path) == ("GET", FILES + "/list")
    assert seen[0].url.params["directory"] == "/dir"


@pytest.mark.parametrize(
    ("method", "args"),
    [("read_file", ("/f",)), ("write_file", ("/f", "x")), ("list_files", ("/d",))],
)
@pytest.mark.parametrize(
    ("status", "exc"),
    [(403, PelicanDenied), (404, PelicanNotFound), (500, PelicanUnavailable)],
)
def test_file_methods_map_errors(
    method: str,
    args: tuple[str, ...],
    status: int,
    exc: type[Exception],
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING", logger="addon.pelican"), pytest.raises(exc) as info:
        run_client(lambda r: httpx.Response(status), method, *args)
    text = " ".join(r.getMessage() for r in caplog.records) + str(info.value)
    assert "pacc_TEST" not in text


@pytest.mark.parametrize(
    ("method", "args"),
    [("read_file", ("/f",)), ("write_file", ("/f", "x")), ("list_files", ("/d",))],
)
def test_file_methods_timeout_is_unavailable(method: str, args: tuple[str, ...]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(PelicanUnavailable):
        run_client(handler, method, *args)


@pytest.mark.parametrize(
    "body",
    [
        [],
        {"data": "x"},
        {"data": [1]},
        {"data": [{"attributes": {"name": "a"}}]},
        {"data": [{"attributes": {"name": 3, "is_file": True}}]},
    ],
)
def test_list_files_bad_shapes_are_unavailable(body: Any) -> None:
    with pytest.raises(PelicanUnavailable):
        run_client(lambda r: httpx.Response(200, json=body), "list_files", "/d")
