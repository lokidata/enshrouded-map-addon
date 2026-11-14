"""Chestsort categories file: parse, validate, canonical dump, diff, backup names (no I/O)."""

import difflib
import hashlib
import json
import re
from collections.abc import Collection
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

_MAX_CATEGORIES = 200
_MAX_NAME = 60
_MAX_STR = 200
_MAX_WORDS = 100
_MAX_ITEMS = 20000
_BUILTIN_GROUPS = {"nourriture"}  # the mod's readme says not to reuse these names


class ChestsortError(Exception):
    def __init__(self, messages: list[str]) -> None:
        super().__init__("; ".join(messages))
        self.messages = messages


@dataclass(frozen=True)
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse(text: str) -> dict[str, Any]:
    try:
        obj = json.loads(text)
    except ValueError as e:
        raise ChestsortError([f"JSON invalide : {e}"]) from e
    if not isinstance(obj, dict):
        raise ChestsortError(["Le fichier doit contenir un objet JSON."])
    return obj


def _not_utf8(s: str) -> bool:
    """A lone surrogate (JSON "\\ud800") parses but cannot be written as UTF-8."""
    try:
        s.encode()
    except UnicodeEncodeError:
        return True
    return False


def _shown(s: str) -> str:
    return s.encode(errors="replace").decode()  # a message must stay valid UTF-8


def _bad_str(s: Any) -> bool:
    return (
        not isinstance(s, str)
        or not s
        or len(s) > _MAX_STR
        or any(ord(c) < 32 or ord(c) == 127 for c in s)
        or _not_utf8(s)
    )


def _check_list(name: str, key: str, v: Any, cap: int, errors: list[str]) -> list[str]:
    if not isinstance(v, list):
        errors.append(f"Catégorie « {name} » : « {key} » doit être une liste.")
        return []
    if len(v) > cap:
        errors.append(f"Catégorie « {name} » : « {key} » dépasse {cap} entrées.")
    if any(_bad_str(s) for s in v):
        errors.append(
            f"Catégorie « {name} » : « {key} » ne doit contenir que des textes non vides"
            f" de {_MAX_STR} caractères au plus, sans retour à la ligne, caractère de contrôle"
            " ni caractère invalide."
        )
        return []
    return list(v)


def validate(obj: dict[str, Any]) -> Report:
    errors: list[str] = []
    warnings: list[str] = []
    readme = obj.get("_readme")
    if "_readme" in obj and (
        not isinstance(readme, list) or not all(isinstance(s, str) for s in readme)
    ):
        errors.append("« _readme » doit être une liste de textes.")
    cats = obj.get("categories")
    if not isinstance(cats, dict):
        errors.append("« categories » doit être un objet.")
        return Report(errors, warnings)
    if not 1 <= len(cats) <= _MAX_CATEGORIES:
        errors.append(f"Il faut de 1 à {_MAX_CATEGORIES} catégories (il y en a {len(cats)}).")
    seen_names: dict[str, str] = {}
    word_owner: dict[str, str] = {}
    for name, cat in cats.items():
        bad = any(ord(c) < 32 or ord(c) == 127 for c in name) or _not_utf8(name)
        if not name or len(name) > _MAX_NAME or bad:
            errors.append(
                f"Le nom de catégorie « {_shown(name[:30])} » est invalide"
                " (nom de 1 à 60 caractères, sans caractère invalide)."
            )
            continue
        low = name.casefold()
        if low in seen_names:
            errors.append(f"Catégorie « {name} » : même nom que « {seen_names[low]} ».")
        seen_names[low] = name
        if not isinstance(cat, dict):
            errors.append(f"Catégorie « {name} » : doit être un objet.")
            continue
        for k in sorted(set(cat) - {"words", "items"}):
            errors.append(f"Catégorie « {name} » : clé inconnue « {_shown(k)} ».")
        for k in ("words", "items"):
            if k not in cat:
                errors.append(f"Catégorie « {name} » : « {k} » manquant.")
        words = _check_list(name, "words", cat.get("words", []), _MAX_WORDS, errors)
        _check_list(name, "items", cat.get("items", []), _MAX_ITEMS, errors)
        if low in _BUILTIN_GROUPS:
            warnings.append(f"Catégorie « {name} » : nom d'un groupe intégré du mod, à éviter.")
        if "items" in cat and isinstance(cat["items"], list) and not cat["items"]:
            warnings.append(f"Catégorie « {name} » : « items » est vide.")
        for w in words:
            o = word_owner.setdefault(w.casefold(), name)
            if o != name:
                warnings.append(f"Le mot « {w} » est dans « {o} » et « {name} ».")
    return Report(errors, warnings)


def dump(obj: dict[str, Any]) -> str:
    # no trailing newline: the mod writes its file without one, so a save shows no spurious diff
    return json.dumps(obj, ensure_ascii=False, indent=2)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def unified_diff(old: str, new: str, context: int = 2, max_lines: int = 400) -> list[str]:
    lines = list(
        difflib.unified_diff(
            old.splitlines(), new.splitlines(), "avant", "après", n=context, lineterm=""
        )
    )
    if len(lines) > max_lines:
        return [*lines[:max_lines], f"... {len(lines) - max_lines} more lines"]
    return lines


def bak_name(base: str, now: datetime, taken: Collection[str] = ()) -> str:
    """Dated name; `-2`, `-3`... when taken (same second, clock stepped back): never overwrite."""
    name, n = f"{base}.bak-{now:%Y%m%d-%H%M%S}", 1
    while (candidate := name if n == 1 else f"{name}-{n}") in taken:
        n += 1
    return candidate


def is_bak_name(base: str, name: str) -> bool:
    pattern = re.escape(base) + r"\.bak-[0-9]{8}-[0-9]{6}(-[1-9][0-9]{0,5})?"
    return re.fullmatch(pattern, name) is not None
