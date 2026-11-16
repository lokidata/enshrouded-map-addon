"""Pelican panel client: status, power and backups (no redirects, URL from config)."""

import logging
import math
import time
from dataclasses import dataclass
from typing import Any, Literal

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


class PelicanRejected(Exception):
    pass


class PelicanBadContent(Exception):
    """The file is not valid UTF-8: it is never decoded lossily (a .bak would be damaged)."""


@dataclass(frozen=True)
class ServerStatus:
    name: str
    state: str
    cpu: float
    memory_bytes: int
    disk_bytes: int
    uptime_ms: int


@dataclass(frozen=True)
class Backup:
    uuid: str
    name: str
    bytes: int
    created_at: str
    completed_at: str | None
    is_successful: bool | None
    is_locked: bool


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
        self._backup_body = {"ignored": settings.backup_ignored} if settings.backup_ignored else {}
        self._last_log: dict[str, float] = {}

    def _fail(self, kind: str, status: int | None, detail: str) -> None:
        """One warning line per distinct reason and minute; never the key or the request headers."""
        detail = " ".join(detail.split())[:200]
        reason = f"{kind} {status} {detail}"
        now = time.monotonic()
        if now - self._last_log.get(reason, -LOG_EVERY) >= LOG_EVERY:
            self._last_log[reason] = now
            log.warning("pelican_error kind=%s status=%s detail=%r", kind, status, detail)

    async def _request(
        self,
        method: str,
        suffix: str,
        body: dict[str, Any] | None = None,
        *,
        params: dict[str, str] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            resp = await self._client.request(
                method,
                self._base + suffix,
                headers=self._headers | (headers or {}),
                params=params,
                content=content,
                json=body,
                timeout=self._timeout,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            # httpx messages never carry request headers; the key stays out of ours too
            self._fail("unreachable", None, type(exc).__name__)
            raise PelicanUnavailable("pelican unreachable") from exc
        code = resp.status_code
        if 200 <= code < 300:  # Pelican may answer 200, 201 or 204; bodies are checked by callers
            return resp
        kinds = {403: "denied", 404: "not_found", 400: "rejected", 409: "rejected", 422: "rejected"}
        if code not in kinds:
            self._fail("unavailable", code, "")
            raise PelicanUnavailable(f"pelican answered {code}")
        self._fail(kinds[code], code, _panel_detail(resp))
        # "rejected" means a refused write; on a GET these codes are an unusable answer
        other = PelicanRejected if method == "POST" else PelicanUnavailable
        raise {403: PelicanDenied, 404: PelicanNotFound}.get(code, other)(code)

    async def _json(self, method: str, suffix: str, body: dict[str, Any] | None = None) -> Any:
        resp = await self._request(method, suffix, body)
        try:
            return resp.json()
        except ValueError as exc:
            self._fail("bad_response", resp.status_code, "invalid JSON")
            raise PelicanUnavailable("pelican sent invalid JSON") from exc

    def _bad(self) -> PelicanUnavailable:
        self._fail("bad_response", 200, "unexpected response shape")
        return PelicanUnavailable("unexpected response shape")

    async def _get(self, suffix: str) -> dict[str, Any]:
        data = await self._json("GET", suffix)
        attrs = data.get("attributes") if isinstance(data, dict) else None
        if not isinstance(attrs, dict):
            raise self._bad()
        return attrs

    async def power(self, signal: Literal["start", "stop", "restart"]) -> None:
        await self._request("POST", "/power", {"signal": signal})

    async def read_file(self, path: str) -> str:
        resp = await self._request("GET", "/files/contents", params={"file": path})
        try:
            return resp.content.decode("utf-8")  # strict; a BOM and CRLF are kept as they are
        except UnicodeDecodeError:
            self._fail("bad_content", resp.status_code, "not utf-8")
            raise PelicanBadContent("file is not utf-8") from None

    async def write_file(self, path: str, text: str) -> None:
        await self._request(
            "POST",
            "/files/write",
            params={"file": path},
            content=text.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
        )

    async def list_files(self, directory: str) -> list[str]:
        resp = await self._request("GET", "/files/list", params={"directory": directory})
        try:
            data = resp.json()
        except ValueError:
            raise self._bad() from None
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise self._bad()
        names: list[str] = []
        for row in rows:
            a = row.get("attributes") if isinstance(row, dict) else None
            if not isinstance(a, dict) or not isinstance(a.get("name"), str):
                raise self._bad()
            if not isinstance(a.get("is_file"), bool):
                raise self._bad()
            if a["is_file"]:
                names.append(a["name"])
        return names

    async def list_backups(self) -> list[Backup]:
        data = await self._json("GET", "/backups")
        rows = data.get("data") if isinstance(data, dict) else None
        if not isinstance(rows, list):
            raise self._bad()
        return [
            self._backup(row.get("attributes") if isinstance(row, dict) else None) for row in rows
        ]

    async def backup(self, uuid: str) -> Backup:
        return self._backup(await self._get(f"/backups/{uuid}"))

    async def download_url(self, uuid: str) -> str:
        """One-time signed URL (a credential: never logged, never journalled)."""
        url = (await self._get(f"/backups/{uuid}/download")).get("url")
        if not (isinstance(url, str) and url.startswith(("https://", "http://"))):
            raise self._bad()
        return url

    async def create_backup(self) -> Backup | None:
        """None: Pelican created it (2xx) but the body could not be parsed (logged)."""
        resp = await self._request("POST", "/backups", self._backup_body)
        try:
            data = resp.json()
        except ValueError:
            data = None
        try:
            return self._backup(data.get("attributes") if isinstance(data, dict) else None)
        except PelicanUnavailable:  # _bad() already logged bad_response
            return None

    def _backup(self, a: Any) -> Backup:
        def opt(key: str, kind: type) -> Any:
            v = a.get(key)
            if v is not None and not isinstance(v, kind):
                raise self._bad()
            return v

        if not isinstance(a, dict):
            raise self._bad()
        uuid, name, created = a.get("uuid"), a.get("name"), a.get("created_at")
        locked = a.get("is_locked")
        if not (isinstance(uuid, str) and isinstance(name, str) and isinstance(created, str)):
            raise self._bad()
        if not isinstance(locked, bool):
            raise self._bad()
        try:
            size = int(_num(a.get("bytes")))
        except PelicanUnavailable:
            raise self._bad() from None
        return Backup(
            uuid, name, size, created, opt("completed_at", str), opt("is_successful", bool), locked
        )

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
