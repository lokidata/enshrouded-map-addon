"""HTTP API: identity relay, access control, status, journal, power and backups."""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from starlette.responses import JSONResponse, Response
from starlette.types import Scope

from addon.config import Settings, get_settings
from addon.identity import Identity, SiteUnavailable, Unauthenticated, who_am_i
from addon.pelican import (
    PelicanClient,
    PelicanDenied,
    PelicanNotFound,
    PelicanRejected,
    PelicanUnavailable,
)
from addon.store import Level, Store
from addon.throttle import Throttle

PUBLIC_JOURNAL = ("at", "username", "action", "target", "result")
PELICAN_ERRORS: dict[type[Exception], tuple[str, int | None]] = {
    PelicanDenied: ("pelican_denied", 403),
    PelicanNotFound: ("pelican_not_found", 404),
    PelicanUnavailable: ("pelican_unavailable", None),
}


POWER_WINDOW = 30  # seconds, global (not per user)
BACKUP_WINDOW = 300
NEEDS_STATE = {"start": "offline", "stop": "running", "restart": "running"}


class AccessBody(BaseModel):
    level: Level | None  # required; null revokes


class PowerBody(BaseModel):
    signal: Literal["start", "stop", "restart"]
    confirm: Any = False  # checked with `is True`: the string "true" is refused


class Refused(Exception):
    def __init__(
        self, code: int, reason: str, status: int | None = None, retry_after: int | None = None
    ) -> None:
        self.code, self.reason, self.status, self.retry_after = code, reason, status, retry_after


def check_write(request: Request) -> None:
    """CSRF guard: a cross-site form cannot set a custom header; Origin pins the site."""
    if request.method == "GET":
        return
    allowed = request.app.state.settings.allowed_origin
    if request.headers.get("x-addon") != "1" or (
        allowed and request.headers.get("origin") != allowed
    ):
        raise HTTPException(403, "forbidden")


async def current(request: Request) -> Identity:
    state = request.app.state
    try:
        return await who_am_i(request.headers.get("cookie"), state.http, state.settings)
    except Unauthenticated as exc:
        raise HTTPException(401, "unauthenticated") from exc
    except SiteUnavailable as exc:
        raise HTTPException(503, "site_unavailable") from exc


Current = Annotated[Identity, Depends(current)]


def level_of(request: Request, who: Identity) -> Level | None:
    return "action" if who.is_admin else request.app.state.store.level_of(who.key)


def require_read(request: Request, who: Current) -> Identity:
    if level_of(request, who) is None:
        raise HTTPException(403, "forbidden")
    return who


def require_admin(who: Current) -> Identity:
    if not who.is_admin:
        raise HTTPException(403, "forbidden")
    return who


def require_action(request: Request, who: Current) -> Identity:
    if level_of(request, who) != "action":
        raise HTTPException(403, "forbidden")
    return who


Reader = Annotated[Identity, Depends(require_read)]
Actor = Annotated[Identity, Depends(require_action)]
Admin = Annotated[Identity, Depends(require_admin)]
router = APIRouter(prefix="/addon/api", dependencies=[Depends(check_write)])


async def site_users(request: Request) -> dict[str, str]:
    """user_key -> username, from the site (admin-only route, the admin's cookie relayed)."""
    state = request.app.state
    try:
        resp = await state.http.get(
            f"{state.settings.site_url.rstrip('/')}/api/v1/auth/users",
            headers={"Cookie": request.headers.get("cookie", "")},
            timeout=state.settings.pelican_timeout,
            follow_redirects=False,
        )
        data: Any = resp.json() if resp.status_code == 200 else None
        users: dict[str, str] = {}
        for u in data:
            if u.get("id") is None or not u.get("created_at"):
                raise ValueError("id and created_at are required for a stable key")
            users[f"{u['id']}:{u['created_at']}"] = str(u["username"])
    except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise HTTPException(503, "site_unavailable") from exc
    return users


@router.get("/me")
def me(request: Request, who: Current) -> dict[str, Any]:
    return {"username": who.username, "is_admin": who.is_admin, "level": level_of(request, who)}


@router.get("/status")
async def status(request: Request, who: Reader) -> dict[str, Any]:
    # not journalled: a 15 s poll per viewer would fill the journal (journal write actions later)
    try:
        result = await request.app.state.pelican.status()
    except (PelicanDenied, PelicanNotFound, PelicanUnavailable) as exc:
        detail, _ = PELICAN_ERRORS[type(exc)]
        raise HTTPException(502, detail) from exc
    return asdict(result)


@router.get("/journal")
def journal(request: Request, who: Reader) -> list[dict[str, Any]]:
    rows = [asdict(r) for r in request.app.state.store.journal()]
    if who.is_admin:
        return rows
    return [{k: r[k] for k in PUBLIC_JOURNAL} for r in rows]


@router.get("/access")
async def list_access(request: Request, who: Admin) -> list[dict[str, Any]]:
    store: Store = request.app.state.store
    users = await site_users(request)
    names = {r.user_key: r.username for r in store.list_access()}
    for key in store.prune_missing(set(users)):
        store.log(who.username, "access", names[key], "removed")
    levels = {r.user_key: r.level for r in store.list_access()}
    return [{"user_key": k, "username": n, "level": levels.get(k)} for k, n in users.items()]


@router.put("/access/{user_key}")
async def set_access(
    request: Request, user_key: str, body: AccessBody, who: Admin
) -> dict[str, Any]:
    if user_key == who.key:
        raise HTTPException(400, "administrator_is_implicit")
    username = (await site_users(request)).get(user_key)
    if username is None:
        raise HTTPException(404, "unknown_user")
    store: Store = request.app.state.store
    if body.level is None:
        store.revoke(user_key)
    else:
        store.grant(user_key, username, body.level, who.username)
    store.log(who.username, "access", username, body.level or "revoked")
    return {"user_key": user_key, "username": username, "level": body.level}


def pelican_refusal(exc: Exception) -> Refused:
    if isinstance(exc, PelicanRejected):
        return Refused(409, "pelican_rejected", exc.args[0] if exc.args else None)
    detail, status = PELICAN_ERRORS[type(exc)]
    return Refused(502, detail, status)


async def journalled(
    request: Request, who: Identity, action: str, target: str, run: Any
) -> dict[str, Any] | JSONResponse:
    """Run one write, journal its outcome (never bodies or secrets), map refusals to HTTP."""
    store: Store = request.app.state.store
    try:
        result: dict[str, Any] = await run()
    except Refused as r:
        store.log(who.username, action, target, r.reason, r.status)
        if r.retry_after is not None:
            return JSONResponse(
                {"detail": r.reason, "retry_after": r.retry_after},
                status_code=429,
                headers={"Retry-After": str(r.retry_after)},
            )
        raise HTTPException(r.code, r.reason) from r
    store.log(who.username, action, target, "ok")
    return result


async def throttled(request: Request, key: str, seconds: int, call: Any) -> Any:
    """Under the lock: refuse inside the window; only a successful call starts it."""
    throttle: Throttle = request.app.state.throttle
    wait = throttle.retry_after(key, seconds)
    if wait is not None:
        raise Refused(429, "rate_limited", retry_after=wait)
    try:
        result = await call()
    except (PelicanDenied, PelicanNotFound, PelicanUnavailable, PelicanRejected) as exc:
        raise pelican_refusal(exc) from exc
    throttle.mark(key)
    return result


@router.post("/power", response_model=None)
async def power(request: Request, who: Actor) -> dict[str, Any] | JSONResponse:
    raw: Any = None
    with suppress(ValueError):  # bad JSON: refused below as invalid_request, and journalled
        raw = json.loads(await request.body())
    sig = raw.get("signal") if isinstance(raw, dict) else None
    # only a short word reaches the journal, never arbitrary input
    target = sig if isinstance(sig, str) and sig.isalpha() and len(sig) <= 16 else "invalid"

    async def run() -> dict[str, Any]:
        try:
            body = PowerBody.model_validate(raw)
        except ValidationError:
            raise Refused(422, "invalid_request") from None
        if body.signal != "start" and body.confirm is not True:
            raise Refused(422, "confirmation_required")
        pelican: PelicanClient = request.app.state.pelican
        async with request.app.state.action_lock:
            try:
                state = (await pelican.status()).state
            except (PelicanDenied, PelicanNotFound, PelicanUnavailable) as exc:
                raise pelican_refusal(exc) from exc
            if state != NEEDS_STATE[body.signal]:
                raise Refused(409, "wrong_state")
            await throttled(request, "power", POWER_WINDOW, lambda: pelican.power(body.signal))
        return {"signal": body.signal, "result": "ok"}

    return await journalled(request, who, "power", target, run)


@router.get("/backups")
async def list_backups(request: Request, who: Reader) -> list[dict[str, Any]]:
    try:
        rows = await request.app.state.pelican.list_backups()
    except (PelicanDenied, PelicanNotFound, PelicanUnavailable) as exc:
        detail, _ = PELICAN_ERRORS[type(exc)]
        raise HTTPException(502, detail) from exc
    return [asdict(b) for b in rows]


@router.post("/backups", response_model=None)
async def create_backup(request: Request, who: Actor) -> dict[str, Any] | JSONResponse:
    async def run() -> dict[str, Any]:
        async with request.app.state.action_lock:
            backup = await throttled(
                request, "backup", BACKUP_WINDOW, request.app.state.pelican.create_backup
            )
        return asdict(backup)

    return await journalled(request, who, "backup", "create", run)


CSP = "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"


class Page(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        resp = await super().get_response(path, scope)
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        return resp


def create_app(
    settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cfg = settings or get_settings()
        async with httpx.AsyncClient(transport=transport) as http:
            app.state.settings = cfg
            app.state.store = Store(cfg.db_path, cfg.journal_days)
            app.state.http = http
            app.state.pelican = PelicanClient(cfg, http)
            app.state.throttle = Throttle()
            app.state.action_lock = asyncio.Lock()  # one power or backup request at a time
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(router)
    app.mount("/addon", Page(directory=Path(__file__).parent / "static", html=True))
    return app
