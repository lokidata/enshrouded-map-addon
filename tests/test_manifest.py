import json
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from addon.api import create_app
from addon.config import Settings
from addon.manifest import build_manifest

SCHEMA = json.loads((Path(__file__).parents[1] / "contract" / "manifest.schema.json").read_text())
ITEM = SCHEMA["properties"]["addons"]["items"]["properties"]


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
    """The parts of the schema that matter, checked by hand (no jsonschema dependency)."""
    path = re.compile(SCHEMA["$defs"]["path"]["pattern"])
    ok = set(m) == set(SCHEMA["required"]) and m["api_version"] == 1
    ok = ok and bool(path.match(m["script"])) and bool(path.match(m["styles"]))
    for a in m["addons"]:
        ok = ok and set(a) == set(ITEM) and a["level"] in ("read", "action")
        ok = ok and bool(re.fullmatch(ITEM["id"]["pattern"], a["id"]))
        ok = ok and bool(re.fullmatch(ITEM["element"]["pattern"], a["element"]))
        ok = ok and set(a["name"]) == {"fr", "en"}
    return ok


@pytest.fixture
def web(tmp_path: Path) -> Path:
    d = tmp_path / "web"
    d.mkdir()
    (d / "main.js").write_text("1")
    (d / "styles.css").write_text("a{}")
    return d


def test_manifest_validates_against_schema(tmp_path: Path, web: Path) -> None:
    m = build_manifest({"server": "read", "chestsort": "action"}, settings(tmp_path), web)
    assert conforms(m) and [a["id"] for a in m["addons"]] == ["server", "chestsort"]
    assert [a["level"] for a in m["addons"]] == ["read", "action"]


def test_manifest_filters_by_level(tmp_path: Path, web: Path) -> None:
    m = build_manifest({"server": None, "chestsort": "read"}, settings(tmp_path), web)
    assert [a["id"] for a in m["addons"]] == ["chestsort"]
    assert (
        build_manifest({"server": None, "chestsort": None}, settings(tmp_path), web)["addons"] == []
    )


def test_chestsort_absent_without_file(tmp_path: Path, web: Path) -> None:
    m = build_manifest({"server": "read", "chestsort": "action"}, settings(tmp_path, False), web)
    assert [a["id"] for a in m["addons"]] == ["server"]


def test_script_and_styles_found_in_static_dir(tmp_path: Path, web: Path) -> None:
    (web / "main.js").unlink()
    (web / "styles.css").unlink()
    (web / "main-ABC123.js").write_text("1")
    (web / "styles-XYZ.css").write_text("a{}")
    m = build_manifest({"server": "read", "chestsort": None}, settings(tmp_path), web)
    assert (m["script"], m["styles"]) == ("/addon/main-ABC123.js", "/addon/styles-XYZ.css")
    assert conforms(m)


def test_manifest_route_401_and_no_cache(tmp_path: Path, web: Path) -> None:
    sessions = {"alice": {"id": 7, "username": "a", "is_admin": True, "created_at": "2026-01-01"}}

    def handler(req: httpx.Request) -> httpx.Response:
        who = req.headers.get("cookie", "").removeprefix("session=")
        return httpx.Response(200, json=sessions[who]) if who in sessions else httpx.Response(401)

    with TestClient(create_app(settings(tmp_path), httpx.MockTransport(handler))) as c:
        assert c.get("/addon/api/manifest").status_code == 401
        r = c.get("/addon/api/manifest", headers={"Cookie": "session=alice"})
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
        assert conforms(r.json()) and len(r.json()["addons"]) == 2
        js = c.get("/addon/main.js")
        assert js.status_code == 200 and js.headers["cache-control"] == "no-cache"


def test_schema_path_rule_refuses_traversal_and_double_slash() -> None:
    path = re.compile(SCHEMA["$defs"]["path"]["pattern"])
    for bad in ("/addon/../x", "/addon//x", "//x", "https://x/y.js", "/other/x.js"):
        assert not path.match(bad)
    assert path.match("/addon/main.js")
