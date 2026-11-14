"""HTTP API: identity relay, access control, status, journal."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import Response
from starlette.types import Scope

from addon.config import Settings, get_settings
from addon.identity import Identity, SiteUnavailable, Unauthenticated, who_am_i
from addon.pelican import PelicanClient, PelicanDenied, PelicanNotFound, PelicanUnavailable
from addon.store import Level, Store

PUBLIC_JOURNAL = ("at", "username", "action", "target", "result")
PELICAN_ERRORS: dict[type[Exception], tuple[str, int | None]] = {
    PelicanDenied: ("pelican_denied", 403),
    PelicanNotFound: ("pelican_not_found", 404),
    PelicanUnavailable: ("pelican_unavailable", None),
}


class AccessBody(BaseModel):
    level: Level | None  # required; null revokes


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


Reader = Annotated[Identity, Depends(require_read)]
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
    store: Store = request.app.state.store
    try:
        result = await request.app.state.pelican.status()
    except (PelicanDenied, PelicanNotFound, PelicanUnavailable) as exc:
        detail, code = PELICAN_ERRORS[type(exc)]
        store.log(who.username, "status", "server", detail, code)
        raise HTTPException(502, detail) from exc
    store.log(who.username, "status", "server", "ok", 200)
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
            yield

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(router)
    app.mount("/addon", Page(directory=Path(__file__).parent / "static", html=True))
    return app
