import asyncio
from typing import Any

import httpx
import pytest

from addon.config import Settings
from addon.pelican import (
    PelicanClient,
    PelicanDenied,
    PelicanNotFound,
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
