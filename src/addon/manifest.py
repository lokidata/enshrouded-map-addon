"""The manifest the site reads (api_version 2). Public: the site filters by level."""

import tomllib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from addon.config import Settings

API_VERSION = 2
NAMES = {
    "server": {"fr": "Serveur", "en": "Server"},
    "chestsort": {"fr": "Coffres", "en": "Chests"},
}
DESCRIPTIONS = {
    "server": {
        "fr": "État du serveur, sauvegardes et redémarrage.",
        "en": "Server status, backups and restart.",
    },
    "chestsort": {
        "fr": "Édition des catégories de tri des coffres.",
        "en": "Edit the chest sorting categories.",
    },
}
ELEMENTS = {"server": "addon-server", "chestsort": "addon-chestsort"}


def _own_version() -> str:
    try:
        return version("enshrouded-map-addon")
    except PackageNotFoundError:
        pass
    # The image runs from /srv/src without installing the package: read pyproject.toml next to src/.
    try:
        text = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
        return str(tomllib.loads(text)["project"]["version"])
    except (OSError, KeyError, ValueError):
        return "0.0.0"


def _find(folder: Path, exact: str, hashed: str) -> str:
    """The built file's public path: `exact` (what `ng build` writes), else a `hashed` match."""
    if (folder / exact).is_file():
        return f"/addon/{exact}"
    found = sorted(p.name for p in folder.glob(hashed)) if folder.is_dir() else []
    return f"/addon/{found[0] if found else exact}"


def build_manifest(settings: Settings, static_dir: Path) -> dict[str, Any]:
    script = _find(static_dir, "main.js", "main-*.js")
    styles = _find(static_dir, "styles.css", "styles-*.css")
    entries = [
        {
            "id": entry_id,
            "version": _own_version(),
            "name": NAMES[entry_id],
            "description": DESCRIPTIONS[entry_id],
            "element": element,
            "capabilities": ["tab"],
            "script": script,
            "styles": styles,
        }
        for entry_id, element in ELEMENTS.items()
        if entry_id != "chestsort" or settings.chestsort_file is not None
    ]
    return {"api_version": API_VERSION, "entries": entries}
