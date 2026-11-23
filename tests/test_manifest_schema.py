"""The real manifest conforms to contract/manifest.schema.json (no jsonschema dependency)."""

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest

from addon.config import Settings
from addon.manifest import build_manifest

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[1] / "contract" / "manifest.schema.json").read_text()
)
ANNOTATIONS = {"$schema", "title", "description"}
TYPES = {"object": dict, "array": list, "string": str}


def errors(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Walk only the keywords the schema uses; fail loudly on any other."""
    if "$ref" in schema:
        ref = schema["$ref"].removeprefix("#/$defs/")
        schema = {**SCHEMA["$defs"][ref], **{k: v for k, v in schema.items() if k != "$ref"}}
    out: list[str] = []
    for kw, arg in schema.items():
        if kw in ANNOTATIONS or kw in ("$defs", "properties"):
            continue
        if kw == "type":
            if not isinstance(value, TYPES[arg]):
                return [f"{path}: not {arg}"]
        elif kw == "const":
            if value != arg:
                out.append(f"{path}: not {arg!r}")
        elif kw == "enum":
            if value not in arg:
                out.append(f"{path}: not in {arg}")
        elif kw == "pattern":
            if not re.search(arg, value):
                out.append(f"{path}: pattern")
        elif kw == "maxLength":
            if len(value) > arg:
                out.append(f"{path}: too long")
        elif kw == "minLength":
            if len(value) < arg:
                out.append(f"{path}: too short")
        elif kw == "maxItems":
            if len(value) > arg:
                out.append(f"{path}: too many")
        elif kw == "minItems":
            if len(value) < arg:
                out.append(f"{path}: too few")
        elif kw == "required":
            out += [f"{path}.{k}: missing" for k in arg if k not in value]
        elif kw == "additionalProperties":
            assert arg is False, "only additionalProperties: false is supported"
            out += [f"{path}.{k}: extra" for k in value if k not in schema.get("properties", {})]
        elif kw == "items":
            for i, item in enumerate(value):
                out += errors(item, arg, f"{path}[{i}]")
        elif kw == "$ref":
            continue
        else:
            raise AssertionError(f"unsupported schema keyword {kw!r} at {path}")
    for name, sub in schema.get("properties", {}).items():
        if isinstance(value, dict) and name in value:
            out += errors(value[name], sub, f"{path}.{name}")
    return out


def manifest(tmp_path: Path, chest: bool) -> dict[str, Any]:
    cfg = Settings(
        pelican_url="https://panel.example.test",
        pelican_api_key="pacc_TEST",  # type: ignore[arg-type]
        pelican_server_id="abcd1234",
        site_url="http://site.example.test",
        db_path=str(tmp_path / "a.db"),
        static_dir=str(tmp_path / "web"),
        chestsort_file="/c.json" if chest else None,
    )
    return build_manifest(cfg, tmp_path / "web")


@pytest.mark.parametrize(("chest", "count"), [(True, 2), (False, 1)])
def test_real_manifest_conforms(tmp_path: Path, chest: bool, count: int) -> None:
    m = manifest(tmp_path, chest)
    assert errors(m, SCHEMA) == [] and len(m["entries"]) == count


def mutate(m: dict[str, Any], fn: Any) -> dict[str, Any]:
    out = copy.deepcopy(m)
    fn(out)
    return out


@pytest.mark.parametrize(
    "bad",
    [
        lambda m: m["entries"][0].update(script="/addon/../x.js"),
        lambda m: m["entries"][0].update(script="/other/main.js"),
        lambda m: m["entries"][0].update(element="server"),
        lambda m: m["entries"][0].update(extra=1),
        lambda m: m.update(api_version=1),
        lambda m: m["entries"][0].update(capabilities=["admin"]),
        lambda m: m["entries"][0]["name"].update(en="x" * 41),
    ],
)
def test_checker_rejects_bad_manifest(tmp_path: Path, bad: Any) -> None:
    assert errors(mutate(manifest(tmp_path, True), bad), SCHEMA)


def test_checker_fails_loudly_on_unknown_keyword() -> None:
    with pytest.raises(AssertionError, match="unsupported"):
        errors({}, {"type": "object", "oneOf": []})
