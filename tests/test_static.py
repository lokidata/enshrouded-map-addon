import re
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from addon.api import create_app
from addon.config import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(
        pelican_url="https://panel.example.test",
        pelican_api_key="pacc_TEST",  # type: ignore[arg-type]
        pelican_server_id="abcd1234",
        site_url="http://site.example.test",
        db_path=str(tmp_path / "addon.db"),
    )
    transport = httpx.MockTransport(lambda r: httpx.Response(500))
    with TestClient(create_app(settings, transport)) as c:
        yield c


def test_page_is_french_with_strict_csp(client: TestClient) -> None:
    resp = client.get("/addon/")
    assert resp.status_code == 200
    assert 'lang="fr"' in resp.text
    assert "default-src 'self'" in resp.headers["content-security-policy"]
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>|<style|\sstyle=|\son\w+=", resp.text, re.I)


def test_no_external_url_and_no_innerhtml(client: TestClient) -> None:
    for path in ("/addon/", "/addon/app.js", "/addon/app.css"):
        text = client.get(path).text
        assert not re.search(r"(https?:)?//[a-z0-9.-]+\.[a-z]{2,}", text, re.I), path
        assert "innerHTML" not in text
    assert client.get("/addon/api/me").status_code == 401  # API untouched


def test_page_has_actions_and_backups_ui(client: TestClient) -> None:
    js = client.get("/addon/app.js").text
    for needle in ("/power", "/backups", "X-Addon", "confirm: true"):
        assert needle in js
    html = client.get("/addon/").text
    assert "<dialog" in html and "J'ai prévenu les joueurs" in html
    for ident in ("actions", "backups", "b-create"):
        assert f'id="{ident}"' in html


def test_action_buttons_start_disabled(client: TestClient) -> None:
    html = client.get("/addon/").text
    for ident in ("act-start", "act-stop", "act-restart", "b-create"):
        tag = re.search(rf'<button[^>]*id="{ident}"[^>]*>', html)
        assert tag and " disabled" in tag.group(0), ident


def test_ui_review_rules(client: TestClient) -> None:
    js = client.get("/addon/app.js").text
    for reason in ("busy:", "pelican_timeout:"):
        assert reason in js
    assert 'state = "";' in js  # a failed status read leaves the state unknown
    assert "b.completed_at === null" in js  # 'en cours' until completed_at is set
    assert "loadJournal()" in js.split("async function act")[1].split("const power")[0]
    assert 'id="b-err"' in client.get("/addon/").text  # list errors cleared on success


def test_unfiltered_backup_warning_is_in_the_page(client: TestClient) -> None:
    js = client.get("/addon/app.js").text
    assert "confirm_full" in js and "backup_filtered" in js
    assert "tous les fichiers" in client.get("/addon/app.js").text + client.get("/addon/").text
