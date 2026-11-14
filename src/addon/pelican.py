"""Pelican panel client, status only (two GETs, no redirects, URL from config)."""

import math
from dataclasses import dataclass
from typing import Any

import httpx

from addon.config import Settings


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


class PelicanClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._base = f"{settings.pelican_url}/api/client/servers/{settings.pelican_server_id}"
        self._headers = {
            "Authorization": f"Bearer {settings.pelican_api_key.get_secret_value()}",
            "Accept": "application/json",
        }
        self._timeout = settings.pelican_timeout
        self._client = client

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
            raise PelicanUnavailable("pelican unreachable") from exc
        if resp.status_code == 403:
            raise PelicanDenied
        if resp.status_code == 404:
            raise PelicanNotFound
        if resp.status_code != 200:
            raise PelicanUnavailable(f"pelican answered {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise PelicanUnavailable("pelican sent invalid JSON") from exc
        attrs = data.get("attributes") if isinstance(data, dict) else None
        if not isinstance(attrs, dict):
            raise PelicanUnavailable("unexpected response shape")
        return attrs

    async def status(self) -> ServerStatus:
        info = await self._get("")
        stats = await self._get("/resources")
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
