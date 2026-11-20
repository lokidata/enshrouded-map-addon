"""The manifest the site reads to list the add-ons the caller may use (contract api_version 1)."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from addon.config import Settings
from addon.store import Level

API_VERSION = 1
NAMES = {
    "server": {"fr": "Serveur", "en": "Server"},
    "chestsort": {"fr": "Coffres", "en": "Chests"},
}
ELEMENTS = {"server": "addon-server", "chestsort": "addon-chestsort"}


def _own_version() -> str:
    try:
        return version("enshrouded-map-addon")
    except PackageNotFoundError:
        return "0.0.0"


def _find(folder: Path, exact: str, hashed: str) -> str:
    """The built file's public path: `exact` (what `ng build` writes), else a `hashed` match."""
    if (folder / exact).is_file():
        return f"/addon/{exact}"
    found = sorted(p.name for p in folder.glob(hashed)) if folder.is_dir() else []
    return f"/addon/{found[0] if found else exact}"


def build_manifest(
    levels: dict[str, Level | None], settings: Settings, static_dir: Path
) -> dict[str, Any]:
    addons = []
    for addon_id, element in ELEMENTS.items():
        level = levels.get(addon_id)
        if level is None or (addon_id == "chestsort" and settings.chestsort_file is None):
            continue
        addons.append(
            {
                "id": addon_id,
                "version": _own_version(),
                "level": level,
                "name": NAMES[addon_id],
                "element": element,
            }
        )
    return {
        "api_version": API_VERSION,
        "script": _find(static_dir, "main.js", "main-*.js"),
        "styles": _find(static_dir, "styles.css", "styles-*.css"),
        "addons": addons,
    }
