from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from addon.api import CSP, create_app
from addon.config import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<html><app-root></app-root></html>")
    (web / "main.js").write_text("console.log(1)")
    settings = Settings(
        pelican_url="https://panel.example.test",
        pelican_api_key="pacc_TEST",  # type: ignore[arg-type]
        pelican_server_id="abcd1234",
        site_url="http://site.example.test",
        db_path=str(tmp_path / "addon.db"),
        static_dir=str(web),
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(500))
    with TestClient(create_app(settings, transport)) as c:
        yield c


def test_deep_link_serves_the_app(client: TestClient) -> None:
    resp = client.get("/addon/mods")
    assert resp.status_code == 200 and "text/html" in resp.headers["content-type"]
    assert "<app-root" in resp.text


def test_real_asset_is_served_as_is(client: TestClient) -> None:
    assert client.get("/addon/main.js").text == "console.log(1)"


def test_unknown_asset_is_404(client: TestClient) -> None:
    assert client.get("/addon/ds/nope.woff2").status_code == 404


def test_unknown_api_path_is_not_html(client: TestClient) -> None:
    resp = client.get("/addon/api/nope")
    assert resp.status_code == 404 and "<app-root" not in resp.text


def test_security_headers_on_the_app_and_on_a_deep_link(client: TestClient) -> None:
    for path in ("/addon/", "/addon/mods"):
        resp = client.get(path)
        assert resp.headers["content-security-policy"] == CSP
        assert resp.headers["x-content-type-options"] == "nosniff"
