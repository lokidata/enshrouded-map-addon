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
