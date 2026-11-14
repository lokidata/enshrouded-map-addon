"""Pelican panel client, status only (two GETs, no redirects, URL from config)."""

import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import httpx

from addon.config import Settings

log = logging.getLogger("addon.pelican")
LOG_EVERY = 60  # seconds: a status poll runs every 15 s per viewer


class PelicanDenied(Exception):
    pass


class PelicanNotFound(Exception):
    pass


class PelicanUnavailable(Exception):
    pass


@dataclass(frozen=True)
class ServerStatus:
    name: str
    state: str
    cpu: float
    memory_bytes: int
    disk_bytes: int
    uptime_ms: int


def _num(value: Any) -> float:
    # bool is an int subclass: reject it as well
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise PelicanUnavailable("unexpected response shape")
    # json.loads accepts NaN/Infinity; int(inf) would raise outside our error handling
    if not math.isfinite(value) or value < 0:
        raise PelicanUnavailable("unexpected response shape")
    return float(value)


def _panel_detail(resp: httpx.Response) -> str:
    """Pelican's own explanation (e.g. the refused IP address), when the body has one."""
    try:
        return str(resp.json()["errors"][0]["detail"])
    except (ValueError, KeyError, IndexError, TypeError):
        return ""


class PelicanClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._base = f"{settings.pelican_url}/api/client/servers/{settings.pelican_server_id}"
        self._headers = {
            "Authorization": f"Bearer {settings.pelican_api_key.get_secret_value()}",
            "Accept": "application/json",
        }
        self._timeout = settings.pelican_timeout
        self._client = client
        self._last_log: dict[str, float] = {}

    def _fail(self, kind: str, status: int | None, detail: str) -> None:
        """One warning line per distinct reason and minute; never the key or the request headers."""
        detail = " ".join(detail.split())[:200]
        reason = f"{kind} {status} {detail}"
        now = time.monotonic()
        if now - self._last_log.get(reason, -LOG_EVERY) >= LOG_EVERY:
            self._last_log[reason] = now
            log.warning("pelican_error kind=%s status=%s detail=%r", kind, status, detail)

    async def _get(self, suffix: str) -> dict[str, Any]:
        try:
            resp = await self._client.get(
                self._base + suffix,
                headers=self._headers,
                timeout=self._timeout,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            # httpx messages never carry request headers; the key stays out of ours too
            self._fail("unreachable", None, type(exc).__name__)
            raise PelicanUnavailable("pelican unreachable") from exc
        if resp.status_code in (403, 404):
            self._fail(
                "denied" if resp.status_code == 403 else "not_found",
                resp.status_code,
                _panel_detail(resp),
            )
            raise PelicanDenied if resp.status_code == 403 else PelicanNotFound
        if resp.status_code != 200:
            self._fail("unavailable", resp.status_code, "")
            raise PelicanUnavailable(f"pelican answered {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            self._fail("bad_response", 200, "invalid JSON")
            raise PelicanUnavailable("pelican sent invalid JSON") from exc
        attrs = data.get("attributes") if isinstance(data, dict) else None
        if not isinstance(attrs, dict):
            self._fail("bad_response", 200, "unexpected response shape")
            raise PelicanUnavailable("unexpected response shape")
        return attrs

    async def status(self) -> ServerStatus:
        info = await self._get("")
        stats = await self._get("/resources")
        try:
            return self._build(info, stats)
        except PelicanUnavailable as exc:
            self._fail("bad_response", 200, str(exc))
            raise

    @staticmethod
    def _build(info: dict[str, Any], stats: dict[str, Any]) -> ServerStatus:
        name, state = info.get("name"), stats.get("current_state")
        res = stats.get("resources")
        if not isinstance(name, str) or not isinstance(state, str) or not isinstance(res, dict):
            raise PelicanUnavailable("unexpected response shape")
        return ServerStatus(
            name,
            state,
            _num(res.get("cpu_absolute")),
            int(_num(res.get("memory_bytes"))),
            int(_num(res.get("disk_bytes"))),
            int(_num(res.get("uptime"))),
        )
