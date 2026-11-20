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


def test_addon_root_redirects_to_site_fragment(client: TestClient) -> None:
    resp = client.get("/addon/", follow_redirects=False)
    assert resp.status_code in (302, 307) and resp.headers["location"] == "/#addon/server"


def test_no_spa_fallback(client: TestClient) -> None:
    # screens are routes of the site: an unknown path under /addon/ is a plain 404
    assert client.get("/addon/mods").status_code == 404
    assert client.get("/addon/index.html").status_code == 404


def test_real_asset_is_served_as_is(client: TestClient) -> None:
    assert client.get("/addon/main.js").text == "console.log(1)"


def test_unknown_asset_is_404(client: TestClient) -> None:
    assert client.get("/addon/nope.woff2").status_code == 404


def test_unknown_api_path_is_not_html(client: TestClient) -> None:
    resp = client.get("/addon/api/nope")
    assert resp.status_code == 404 and "<app-root" not in resp.text


def test_security_headers_on_the_script(client: TestClient) -> None:
    resp = client.get("/addon/main.js")
    assert resp.headers["content-security-policy"] == CSP
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_missing_ui_folder_is_404_not_a_crash(tmp_path: Path) -> None:
    settings = Settings(
        pelican_url="https://panel.example.test",
        pelican_api_key="pacc_TEST",  # type: ignore[arg-type]
        pelican_server_id="abcd1234",
        site_url="http://site.example.test",
        db_path=str(tmp_path / "addon.db"),
        static_dir=str(tmp_path / "not-built"),
    )
    with TestClient(create_app(settings, httpx.MockTransport(lambda r: httpx.Response(500)))) as c:
        assert c.get("/addon/main.js").status_code == 404
