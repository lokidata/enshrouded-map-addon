import re
import tomllib
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from addon import manifest
from addon.api import create_app
from addon.config import Settings
from addon.manifest import build_manifest

PATH = re.compile(r"(?!.*(\.\.|//))/addon/[A-Za-z0-9._/-]{1,100}")
ENTRY_KEYS = {"id", "version", "name", "description", "element", "capabilities", "script", "styles"}


def settings(tmp_path: Path, chest: bool = True) -> Settings:
    return Settings(
        pelican_url="https://panel.example.test",
        pelican_api_key="pacc_TEST",  # type: ignore[arg-type]
        pelican_server_id="abcd1234",
        site_url="http://site.example.test",
        db_path=str(tmp_path / "a.db"),
        static_dir=str(tmp_path / "web"),
        chestsort_file="/c.json" if chest else None,
    )


def conforms(m: dict[str, Any]) -> bool:
    """What the site's `parse_manifest` requires, checked by hand."""
    ok = set(m) == {"api_version", "entries"} and m["api_version"] == 2
    for e in m["entries"]:
        ok = ok and set(e) == ENTRY_KEYS and e["capabilities"] == ["tab"]
        ok = ok and bool(re.fullmatch(r"[a-z0-9-]{1,20}", e["id"]))
        ok = ok and bool(re.fullmatch(r"addon-[a-z0-9-]{1,30}", e["element"]))
        ok = ok and bool(PATH.fullmatch(e["script"])) and bool(PATH.fullmatch(e["styles"]))
        ok = ok and 1 <= len(e["version"]) <= 20
        for field, limit in (("name", 40), ("description", 200)):
            ok = ok and set(e[field]) == {"fr", "en"}
            ok = ok and all(1 <= len(v) <= limit for v in e[field].values())
    return ok


@pytest.fixture
def web(tmp_path: Path) -> Path:
    d = tmp_path / "web"
    d.mkdir()
    (d / "main.js").write_text("1")
    (d / "styles.css").write_text("a{}")
    return d


def test_manifest_lists_both_entries(tmp_path: Path, web: Path) -> None:
    m = build_manifest(settings(tmp_path), web)
    assert conforms(m) and [e["id"] for e in m["entries"]] == ["server", "chestsort"]
    assert {e["script"] for e in m["entries"]} == {"/addon/main.js"}


def test_chestsort_absent_without_file(tmp_path: Path, web: Path) -> None:
    m = build_manifest(settings(tmp_path, False), web)
    assert conforms(m) and [e["id"] for e in m["entries"]] == ["server"]


def test_script_and_styles_found_in_static_dir(tmp_path: Path, web: Path) -> None:
    (web / "main.js").unlink()
    (web / "styles.css").unlink()
    (web / "main-ABC123.js").write_text("1")
    (web / "styles-XYZ.css").write_text("a{}")
    m = build_manifest(settings(tmp_path), web)
    e = m["entries"][0]
    assert (e["script"], e["styles"]) == ("/addon/main-ABC123.js", "/addon/styles-XYZ.css")
    assert conforms(m)


def test_manifest_route_is_public_and_not_cached(tmp_path: Path, web: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        raise AssertionError("the manifest must not call the site")

    with TestClient(create_app(settings(tmp_path), httpx.MockTransport(handler))) as c:
        r = c.get("/addon/api/manifest")
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
        assert conforms(r.json()) and len(r.json()["entries"]) == 2
        js = c.get("/addon/main.js")
        assert js.status_code == 200 and js.headers["cache-control"] == "no-cache"


def test_manifest_route_omits_chestsort_when_unset(tmp_path: Path, web: Path) -> None:
    app = create_app(settings(tmp_path, False), httpx.MockTransport(lambda r: httpx.Response(500)))
    with TestClient(app) as c:
        assert [e["id"] for e in c.get("/addon/api/manifest").json()["entries"]] == ["server"]


def test_version_is_read_from_pyproject_when_the_package_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_: str) -> str:
        raise PackageNotFoundError

    monkeypatch.setattr(manifest, "version", missing)
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    expected = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    assert manifest._own_version() == expected != "0.0.0"


def test_french_descriptions_keep_their_accents() -> None:
    texts = " ".join(d["fr"] for d in manifest.DESCRIPTIONS.values())
    assert (
        "État" in texts and "redémarrage" in texts and "Édition" in texts and "catégories" in texts
    )
