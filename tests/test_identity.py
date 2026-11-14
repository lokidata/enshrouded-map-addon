import asyncio
from typing import Any

import httpx
import pytest

from addon.config import Settings
from addon.identity import Identity, SiteUnavailable, Unauthenticated, who_am_i

SETTINGS = Settings(
    pelican_url="https://panel.example.test",
    pelican_api_key="pacc_TEST",  # type: ignore[arg-type]
    pelican_server_id="abcd1234",
    site_url="http://site.example.test/",
)
ME = {"username": "alice", "is_admin": False, "id": 7, "created_at": "2026-01-02T03:04:05"}


def call(handler: Any, cookie: str | None = "session=abc") -> Identity:
    async def run() -> Identity:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            return await who_am_i(cookie, client, SETTINGS)

    return asyncio.run(run())


def json_handler(body: Any, status: int = 200) -> Any:
    return lambda request: httpx.Response(status, json=body)


def test_valid_identity_and_only_cookie_forwarded() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=ME)

    assert call(handler) == Identity("7:2026-01-02T03:04:05", "alice", False)
    req = seen[0]
    assert str(req.url) == "http://site.example.test/api/v1/auth/me"
    assert req.headers["cookie"] == "session=abc"
    assert "authorization" not in req.headers and "x-addon" not in req.headers


def test_logged_out_or_401_is_unauthenticated() -> None:
    with pytest.raises(Unauthenticated):
        call(json_handler({**ME, "username": None}))
    with pytest.raises(Unauthenticated):
        call(json_handler({}, 401))


def test_no_cookie_makes_no_call() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("network call")

    for cookie in (None, ""):
        with pytest.raises(Unauthenticated):
            call(handler, cookie)


def test_site_failures_are_unavailable() -> None:
    def timeout(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    bad = [
        json_handler({}, 500),
        timeout,
        lambda r: httpx.Response(200, content=b"<html>"),
        lambda r: httpx.Response(302, headers={"location": "/login"}),
        lambda r: httpx.Response(200, json=["x"]),
        json_handler({"username": "a", "is_admin": False, "created_at": "t"}),
        json_handler({"username": "a", "is_admin": False, "id": 1}),
    ]
    for handler in bad:
        with pytest.raises(SiteUnavailable):
            call(handler)


def test_is_admin_only_for_json_true() -> None:
    for value in ("false", "yes", 1, [1], {"a": 1}):
        assert not call(json_handler({**ME, "is_admin": value})).is_admin
    assert call(json_handler({**ME, "is_admin": True})).is_admin
