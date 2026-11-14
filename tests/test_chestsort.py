import copy
import json
from datetime import UTC, datetime
from typing import Any

import pytest

from addon import chestsort as cs

SAMPLE = {
    "_readme": ["Fichier d'exemple.", "Rechargé sans redémarrage."],
    "categories": {
        "Métaux": {"words": ["fer", "étain"], "items": ["Iron_Bar", "Tin_*"]},
        "Plantes": {"words": ["fleur"], "items": ["Herb_01"]},
        "Armes à distance": {"words": ["arc"], "items": ["Bow_01"]},
    },
}


def sample() -> dict[str, Any]:
    return copy.deepcopy(SAMPLE)


def test_round_trip_keeps_accents_and_order() -> None:
    # the mod's own file has no trailing newline: dumping must not add one (no noise in the diff)
    text = json.dumps(SAMPLE, ensure_ascii=False, indent=2)
    assert cs.dump(cs.parse(text)) == text
    assert "Métaux" in text


def test_dump_keeps_key_order() -> None:
    obj = {"categories": sample()["categories"], "_readme": ["x"], "extra": 1}
    assert list(json.loads(cs.dump(obj))) == ["categories", "_readme", "extra"]


@pytest.mark.parametrize("text", ["", "{", "[]", "3", "null"])
def test_parse_refuses_non_object(text: str) -> None:
    with pytest.raises(cs.ChestsortError) as e:
        cs.parse(text)
    assert e.value.messages


def test_sample_is_valid_without_noise() -> None:
    r = cs.validate(sample())
    assert r.errors == [] and r.warnings == []


def _mut(f: Any) -> dict[str, Any]:
    o = sample()
    f(o)
    return o


def _cat(o: dict[str, Any]) -> dict[str, Any]:
    c: dict[str, Any] = o["categories"]["Plantes"]
    return c


BAD: list[tuple[str, dict[str, Any], str]] = [
    ("no categories", _mut(lambda o: o.pop("categories")), "categories"),
    ("categories list", _mut(lambda o: o.update(categories=[])), "categories"),
    ("zero categories", _mut(lambda o: o.update(categories={})), "1 à 200"),
    (
        "201 categories",
        _mut(
            lambda o: o.update(categories={f"c{i}": {"words": [], "items": []} for i in range(201)})
        ),
        "1 à 200",
    ),
    ("category not object", _mut(lambda o: o["categories"].update(Plantes=[])), "Plantes"),
    ("extra key", _mut(lambda o: _cat(o).update(extra=[])), "extra"),
    ("missing words", _mut(lambda o: _cat(o).pop("words")), "words"),
    ("missing items", _mut(lambda o: _cat(o).pop("items")), "items"),
    ("words string", _mut(lambda o: _cat(o).update(words="fleur")), "words"),
    ("items string", _mut(lambda o: _cat(o).update(items="Herb")), "items"),
    ("empty string", _mut(lambda o: _cat(o).update(words=[""])), "Plantes"),
    ("non string", _mut(lambda o: _cat(o).update(words=[3])), "Plantes"),
    ("too long", _mut(lambda o: _cat(o).update(items=["a" * 201])), "200"),
    ("newline", _mut(lambda o: _cat(o).update(words=["a\nb"])), "Plantes"),
    ("control char", _mut(lambda o: _cat(o).update(words=["a\x00b"])), "Plantes"),
    ("101 words", _mut(lambda o: _cat(o).update(words=[f"w{i}" for i in range(101)])), "100"),
    ("20001 items", _mut(lambda o: _cat(o).update(items=[f"i{i}" for i in range(20001)])), "20000"),
    ("empty name", _mut(lambda o: o["categories"].update({"": {"words": [], "items": []}})), "nom"),
    (
        "61 char name",
        _mut(lambda o: o["categories"].update({"n" * 61: {"words": [], "items": []}})),
        "60",
    ),
    (
        "duplicate name",
        _mut(lambda o: o["categories"].update(PLANTES={"words": [], "items": []})),
        "PLANTES",
    ),
    ("readme not list", _mut(lambda o: o.update(_readme="x")), "_readme"),
    ("readme not strings", _mut(lambda o: o.update(_readme=[1])), "_readme"),
]


@pytest.mark.parametrize(("obj", "needle"), [(o, n) for _, o, n in BAD], ids=[b[0] for b in BAD])
def test_validate_errors(obj: dict[str, Any], needle: str) -> None:
    r = cs.validate(obj)
    assert any(needle in m for m in r.errors), r.errors


def test_limits_are_inclusive() -> None:
    o = sample()
    _cat(o).update(words=["w"] * 100, items=["i"] * 20000)
    o["categories"]["n" * 60] = {"words": [], "items": ["x" * 200]}
    assert cs.validate(o).errors == []


def test_unknown_top_level_keys_are_kept() -> None:
    o = sample()
    o["version"] = 2
    assert cs.validate(o).errors == []
    assert json.loads(cs.dump(o))["version"] == 2


def test_warnings() -> None:
    o = sample()
    o["categories"]["Armes à distance"]["words"].append("FER")
    o["categories"]["Nourriture"] = {"words": ["pain"], "items": []}
    r = cs.validate(o)
    assert r.errors == []
    assert any("fer" in w.lower() and "Métaux" in w for w in r.warnings)
    assert any("Nourriture" in w and "intégré" in w for w in r.warnings)
    assert any("Nourriture" in w and "vide" in w for w in r.warnings)


def test_sha256() -> None:
    assert len(cs.sha256("é")) == 64
    assert cs.sha256("a") == cs.sha256("a") != cs.sha256("b")


def test_unified_diff() -> None:
    old = "a\nb\nc\n"
    assert cs.unified_diff(old, old) == []
    d = cs.unified_diff(old, "a\nB\nc\n")
    assert "-b" in d and "+B" in d


def test_unified_diff_truncates() -> None:
    d = cs.unified_diff("", "".join(f"l{i}\n" for i in range(1000)), max_lines=10)
    assert len(d) == 11 and d[-1].startswith("... ") and d[-1].endswith("more lines")


def test_bak_name() -> None:
    now = datetime(2026, 11, 14, 9, 8, 7, tzinfo=UTC)
    n = cs.bak_name("chestsort_categories.json", now)
    assert n == "chestsort_categories.json.bak-20261114-090807"
    assert cs.is_bak_name("chestsort_categories.json", n)


@pytest.mark.parametrize(
    "name",
    [
        "chestsort_categories.json",
        "chestsort_categories.json.bak-20261114-09080",
        "chestsort_categories.json.bak-20261114-090807x",
        "chestsort_categories.json.bak-20261114-090807.txt",
        "x/chestsort_categories.json.bak-20261114-090807",
        "../chestsort_categories.json.bak-20261114-090807",
        "other.json.bak-20261114-090807",
        "chestsort_categories.json.bak-20261114-090807\n",
        "chestsort_categories.json.bak-２０２６1114-090807",
    ],
)
def test_is_bak_name_rejects(name: str) -> None:
    assert not cs.is_bak_name("chestsort_categories.json", name)
