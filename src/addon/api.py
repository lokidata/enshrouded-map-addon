"""HTTP API: identity relay, access control, status, journal, power, backups, chestsort."""

import asyncio
import json
import logging
import posixpath
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
from starlette.responses import JSONResponse, Response
from starlette.types import Scope

from addon import chestsort
from addon.config import Settings, get_settings
from addon.identity import Identity, SiteUnavailable, Unauthenticated, who_am_i
from addon.pelican import (
    PelicanBadContent,
    PelicanClient,
    PelicanDenied,
    PelicanNotFound,
    PelicanRejected,
    PelicanUnavailable,
)
from addon.store import Level, Store
from addon.throttle import Throttle

log = logging.getLogger("addon.api")
PUBLIC_JOURNAL = ("at", "username", "action", "target", "result")
PELICAN_ERRORS: dict[type[Exception], tuple[str, int | None]] = {
    PelicanDenied: ("pelican_denied", 403),
    PelicanNotFound: ("pelican_not_found", 404),
    PelicanUnavailable: ("pelican_unavailable", None),
}


PELICAN_FAILURES = (PelicanDenied, PelicanNotFound, PelicanUnavailable, PelicanRejected)
POWER_WINDOW = 30  # seconds, global (not per user)
BACKUP_WINDOW = 300
LOCK_WAIT = 5  # seconds a second action waits for the lock before `busy`
ACTION_TIMEOUT = 25  # seconds for the whole locked section (status read + Pelican call)
CHESTSORT_WINDOW = 10
PREVIEW_WINDOW = 1  # global; a preview reads the file and runs a diff
ROLLBACK_TIMEOUT = 10  # fresh budget for the rollback after ACTION_TIMEOUT fired
MAX_BYTES = 1_000_000  # chestsort file and request bodies
BACKUPS_SHOWN = 20
NEEDS_STATE = {"start": "offline", "stop": "running", "restart": "running"}


class AccessBody(BaseModel):
    level: Level | None  # required; null revokes


class PowerBody(BaseModel):
    signal: Literal["start", "stop", "restart"]
    confirm: Any = False  # checked with `is True`: the string "true" is refused


class Refused(Exception):
    def __init__(
        self,
        code: int,
        reason: str,
        status: int | None = None,
        retry_after: int | None = None,
        journal: str | None = None,  # journal result when it differs from the response detail
        errors: list[str] | None = None,  # validation messages, sent back but never journalled
        backup: str | None = None,  # the .bak to restore from when a rollback failed
    ) -> None:
        self.code, self.reason, self.status, self.retry_after = code, reason, status, retry_after
        self.journal, self.errors, self.backup = journal or reason, errors, backup


def check_write(request: Request) -> None:
    """CSRF guard: a cross-site form cannot set a custom header; Origin pins the site."""
    if request.method == "GET":
        return
    allowed = request.app.state.settings.allowed_origin
    if request.headers.get("x-addon") != "1":
        log.warning("write_refused reason=missing_header")
        raise HTTPException(403, "forbidden")
    if allowed and request.headers.get("origin") != allowed:
        # the received value is not logged (it is attacker-controlled); check ALLOWED_ORIGIN
        log.warning("write_refused reason=origin_mismatch")
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
    return {
        "username": who.username,
        "is_admin": who.is_admin,
        "level": level_of(request, who),
        "backup_filtered": bool(request.app.state.settings.backup_ignored),
        "chestsort": request.app.state.settings.chestsort_file is not None,
    }


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
        store.log(who.username, action, target, r.journal, r.status)
        if r.retry_after is not None:
            return JSONResponse(
                {"detail": r.reason, "retry_after": r.retry_after},
                status_code=429,
                headers={"Retry-After": str(r.retry_after)},
            )
        if r.errors:
            return JSONResponse({"detail": r.reason, "errors": r.errors}, status_code=r.code)
        if r.backup:
            return JSONResponse({"detail": r.reason, "backup": r.backup}, status_code=r.code)
        raise HTTPException(r.code, r.reason) from r
    except Exception:  # a bug must not hide an attempt that may have reached Pelican
        log.exception("internal_error action=%s", action)  # target is journalled, not logged
        store.log(who.username, action, target, "internal_error")
        return JSONResponse({"detail": "internal_error"}, status_code=500)
    store.log(who.username, action, target, "ok")
    return result


async def throttled(request: Request, key: str, seconds: int, call: Any) -> Any:
    """Under the lock: refuse inside the window; a call that may have applied starts it."""
    throttle: Throttle = request.app.state.throttle
    wait = throttle.retry_after(key, seconds)
    if wait is not None:
        raise Refused(429, "rate_limited", retry_after=wait)
    try:
        result = await call()
    except (PelicanDenied, PelicanNotFound, PelicanUnavailable, PelicanRejected) as exc:
        if isinstance(exc, PelicanUnavailable):  # timeout or 5xx: Pelican may have acted
            throttle.mark(key)
        raise pelican_refusal(exc) from exc
    throttle.mark(key)
    return result


async def locked(
    request: Request,
    key: str,
    work: Any,
    on_timeout: Callable[[], Awaitable[None]] | None = None,
) -> Any:
    """One action at a time, bounded: wait LOCK_WAIT for the lock, ACTION_TIMEOUT inside it.

    `on_timeout` runs still under the lock, outside the cancelled work; it may raise its Refused.
    """
    lock: asyncio.Lock = request.app.state.action_lock
    try:
        await asyncio.wait_for(lock.acquire(), LOCK_WAIT)
    except TimeoutError:
        raise Refused(409, "busy") from None
    try:
        async with asyncio.timeout(ACTION_TIMEOUT):
            return await work()
    except TimeoutError:
        request.app.state.throttle.mark(key)  # outcome unknown: Pelican may have acted
        if on_timeout is not None:
            await on_timeout()
        raise Refused(504, "pelican_timeout", journal="timeout") from None
    finally:
        lock.release()


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

        async def work() -> None:
            try:
                state = (await pelican.status()).state
            except (PelicanDenied, PelicanNotFound, PelicanUnavailable) as exc:
                raise pelican_refusal(exc) from exc
            if state != NEEDS_STATE[body.signal]:
                raise Refused(409, "wrong_state")
            await throttled(request, "power", POWER_WINDOW, lambda: pelican.power(body.signal))

        await locked(request, "power", work)
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
    raw: Any = None
    with suppress(ValueError):  # no or bad body: only matters when the backup is unfiltered
        raw = json.loads(await request.body())
    confirmed = isinstance(raw, dict) and raw.get("confirm_full") is True

    async def run() -> dict[str, Any]:
        # no BACKUP_IGNORED: Pelican would archive every file of the server (tens of GB)
        if not request.app.state.settings.backup_ignored and not confirmed:
            raise Refused(422, "full_backup_confirmation_required")
        backup = await locked(
            request,
            "backup",
            lambda: throttled(
                request, "backup", BACKUP_WINDOW, request.app.state.pelican.create_backup
            ),
        )
        # None: created (2xx) but the body could not be parsed; the list shows it later
        return {"backup": None} if backup is None else asdict(backup)

    return await journalled(request, who, "backup", "create", run)


class PreviewBody(BaseModel):
    categories: Any  # checked by chestsort.validate


class SaveBody(PreviewBody):
    base_hash: str
    confirm: Any = False  # checked with `is True`


class RestoreBody(BaseModel):
    name: str
    base_hash: str
    confirm: Any = False


def chestsort_path(request: Request) -> str:
    """The configured file (never taken from a request); unset means the feature is off."""
    path: str | None = request.app.state.settings.chestsort_file
    if path is None:
        raise HTTPException(404, "Not Found")
    return path


ChestPath = Annotated[str, Depends(chestsort_path)]


async def read_json(request: Request, model: type[Any]) -> Any:
    """Body refused over MAX_BYTES while streaming, before any parsing."""
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_BYTES:
            raise Refused(413, "too_large")
        chunks.append(chunk)
    try:
        return model.model_validate(json.loads(b"".join(chunks)))
    # ValidationError is a ValueError; RecursionError: a deeply nested body
    except (ValueError, ValidationError, RecursionError):
        raise Refused(422, "invalid_request") from None


def check_categories(categories: Any) -> chestsort.Report:
    return chestsort.validate({"categories": categories})


async def read_text(pelican: PelicanClient, path: str) -> str:
    try:
        text: str = await pelican.read_file(path)
    except PelicanBadContent:
        raise Refused(422, "file_not_utf8") from None  # never decoded lossily, nothing written
    if len(text.encode()) > MAX_BYTES:
        raise Refused(413, "too_large")
    return text


async def current_file(request: Request, path: str) -> tuple[str, dict[str, Any]]:
    """For the read-only routes: the file and its parsed object, errors mapped to HTTP."""
    try:
        text = await read_text(request.app.state.pelican, path)
        return text, chestsort.parse(text)
    except Refused as r:
        raise HTTPException(r.code, r.reason) from None
    except chestsort.ChestsortError:
        raise HTTPException(502, "file_invalid") from None
    except (PelicanDenied, PelicanNotFound, PelicanUnavailable) as exc:
        raise HTTPException(502, PELICAN_ERRORS[type(exc)][0]) from exc


NewText = Callable[[str], Awaitable[tuple[str, dict[str, Any]]]]


async def same_text(pelican: PelicanClient, path: str, expected: str) -> bool:
    """Read-back check; any failure to read counts as a mismatch."""
    try:
        return await pelican.read_file(path) == expected
    except (*PELICAN_FAILURES, PelicanBadContent):
        return False


async def rollback(pelican: PelicanClient, undo: dict[str, str]) -> bool:
    try:
        await pelican.write_file(undo["path"], undo["current"])
    except PELICAN_FAILURES:
        return False
    return await same_text(pelican, undo["path"], undo["current"])


async def replace_file(
    request: Request, path: str, base_hash: str, new: NewText, undo: dict[str, str]
) -> dict[str, Any]:
    """Read, check the hash, back up and verify, write, verify, roll back on any failure.

    `undo` is filled once the new write is attempted, for the rollback after a timeout.
    """
    pelican: PelicanClient = request.app.state.pelican
    current = await read_text(pelican, path)
    if chestsort.sha256(current) != base_hash:
        raise Refused(409, "changed_elsewhere")
    text, obj = await new(current)
    folder, base = posixpath.split(path)
    # under the lock: a name already in the folder is never reused (it may be the only copy)
    backup = chestsort.bak_name(base, datetime.now(UTC), set(await pelican.list_files(folder)))
    await pelican.write_file(posixpath.join(folder, backup), current)
    if not await same_text(pelican, posixpath.join(folder, backup), current):
        raise Refused(502, "backup_failed")  # the new content is never written without a copy
    undo.update(path=path, current=current, backup=backup)
    try:
        await pelican.write_file(path, text)
    except (PelicanDenied, PelicanNotFound, PelicanRejected):
        undo.clear()  # a definitive refusal: nothing was applied, no rollback, no window
        raise
    except PelicanUnavailable:  # 5xx or unreachable: the file may be half written
        verified = False
    else:
        verified = await same_text(pelican, path, text)
    if not verified:
        request.app.state.throttle.mark("chestsort")  # the new content may have been applied
        if not await rollback(pelican, undo):
            raise Refused(502, "rollback_failed", backup=backup)
        raise Refused(502, "verify_failed", journal="rolled_back")
    cats = obj["categories"]
    items = sum(len(c["items"]) for c in cats.values())
    log.info("chestsort_written categories=%d items=%d bak=%s", len(cats), items, backup)
    return {"backup": backup, "hash": chestsort.sha256(text)}


async def chestsort_locked(
    request: Request, call: Callable[[dict[str, str]], Awaitable[Any]]
) -> Any:
    """Shares the action lock; save and restore share one 10 s window.

    A timeout after the new write was attempted rolls back with a fresh ROLLBACK_TIMEOUT.
    """
    undo: dict[str, str] = {}

    async def after_timeout() -> None:
        if not undo:
            return  # the new content was never sent
        try:
            restored = await asyncio.wait_for(
                rollback(request.app.state.pelican, undo), ROLLBACK_TIMEOUT
            )
        except TimeoutError:
            restored = False
        if not restored:
            raise Refused(502, "rollback_failed", journal="timeout", backup=undo["backup"])
        raise Refused(504, "pelican_timeout", journal="timeout_rolled_back")

    return await locked(
        request,
        "chestsort",
        lambda: throttled(request, "chestsort", CHESTSORT_WINDOW, lambda: call(undo)),
        after_timeout,
    )


@router.get("/chestsort")
async def chestsort_view(request: Request, path: ChestPath, who: Reader) -> dict[str, Any]:
    text, obj = await current_file(request, path)
    return {
        "categories": obj.get("categories"),
        "other_keys_kept": bool(set(obj) - {"_readme", "categories"}),
        "hash": chestsort.sha256(text),
        "bytes": len(text.encode()),
    }


@router.post("/chestsort/preview", response_model=None)
async def chestsort_preview(
    request: Request, path: ChestPath, who: Actor
) -> dict[str, Any] | JSONResponse:
    # not journalled; no lock (it writes nothing), but one per second for everyone
    throttle: Throttle = request.app.state.throttle
    if (wait := throttle.retry_after("chestsort_preview", PREVIEW_WINDOW)) is not None:
        return JSONResponse(
            {"detail": "rate_limited", "retry_after": wait},
            status_code=429,
            headers={"Retry-After": str(wait)},
        )
    throttle.mark("chestsort_preview")
    try:
        body = await read_json(request, PreviewBody)
    except Refused as r:
        raise HTTPException(r.code, r.reason) from None
    current, obj = await current_file(request, path)
    report = check_categories(body.categories)
    text = chestsort.dump({**obj, "categories": body.categories})
    # "replace": a lone surrogate (an error in the report) must not raise here nor in the answer
    shown = text.encode(errors="replace")
    if len(shown) > MAX_BYTES:
        raise HTTPException(413, "too_large")
    return {
        "errors": report.errors,
        "warnings": report.warnings,
        "diff": await asyncio.to_thread(chestsort.unified_diff, current, shown.decode()),
        "changed": text != current,
    }


@router.put("/chestsort", response_model=None)
async def chestsort_save(
    request: Request, path: ChestPath, who: Actor
) -> dict[str, Any] | JSONResponse:
    async def run() -> dict[str, Any]:
        body: SaveBody = await read_json(request, SaveBody)
        if body.confirm is not True:
            raise Refused(422, "confirmation_required")
        if errors := check_categories(body.categories).errors:
            raise Refused(422, "invalid_content", errors=errors)

        async def merged(current: str) -> tuple[str, dict[str, Any]]:
            try:
                obj = {**chestsort.parse(current), "categories": body.categories}
            except chestsort.ChestsortError:
                raise Refused(502, "file_invalid") from None
            text = chestsort.dump(obj)  # _readme and unknown keys kept, in their order
            if len(text.encode()) > MAX_BYTES:
                raise Refused(413, "too_large")
            return text, obj

        result: dict[str, Any] = await chestsort_locked(
            request, lambda undo: replace_file(request, path, body.base_hash, merged, undo)
        )
        return result

    return await journalled(request, who, "chestsort", "save", run)


@router.get("/chestsort/backups")
async def chestsort_backups(request: Request, path: ChestPath, who: Reader) -> list[str]:
    folder, base = posixpath.split(path)
    try:
        names = await request.app.state.pelican.list_files(folder)
    except (PelicanDenied, PelicanNotFound, PelicanUnavailable) as exc:
        raise HTTPException(502, PELICAN_ERRORS[type(exc)][0]) from exc
    # the timestamp in the name sorts it
    return sorted((n for n in names if chestsort.is_bak_name(base, n)), reverse=True)[
        :BACKUPS_SHOWN
    ]


@router.post("/chestsort/restore", response_model=None)
async def chestsort_restore(
    request: Request, path: ChestPath, who: Actor
) -> dict[str, Any] | JSONResponse:
    folder, base = posixpath.split(path)
    pelican: PelicanClient = request.app.state.pelican

    async def run() -> dict[str, Any]:
        body: RestoreBody = await read_json(request, RestoreBody)
        if body.confirm is not True:
            raise Refused(422, "confirmation_required")
        if not chestsort.is_bak_name(base, body.name):  # never a free path
            raise Refused(422, "invalid_backup_name")

        async def from_backup(_current: str) -> tuple[str, dict[str, Any]]:
            text = await read_text(pelican, posixpath.join(folder, body.name))
            try:
                obj = chestsort.parse(text)
            except chestsort.ChestsortError as e:
                raise Refused(422, "invalid_content", errors=e.messages) from None
            if errors := chestsort.validate(obj).errors:
                raise Refused(422, "invalid_content", errors=errors)
            return text, obj  # restored byte for byte

        async def work(undo: dict[str, str]) -> dict[str, Any]:
            if body.name not in await pelican.list_files(folder):
                raise Refused(404, "unknown_backup")
            return await replace_file(request, path, body.base_hash, from_backup, undo)

        result: dict[str, Any] = await chestsort_locked(request, work)
        return result

    return await journalled(request, who, "chestsort", "restore", run)


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
