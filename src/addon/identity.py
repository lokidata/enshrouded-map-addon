"""Who is the caller? Relay the site session cookie to the site, never handle passwords."""

from dataclasses import dataclass

import httpx

from addon.config import Settings


class Unauthenticated(Exception):
    pass


class SiteUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    key: str  # "<id>:<created_at>": site ids can be reused, the pair cannot
    username: str
    is_admin: bool


async def who_am_i(
    cookie_header: str | None, client: httpx.AsyncClient, settings: Settings
) -> Identity:
    if not cookie_header:
        raise Unauthenticated
    url = f"{settings.site_url.rstrip('/')}/api/v1/auth/me"
    try:
        resp = await client.get(
            url,
            headers={"Cookie": cookie_header},
            timeout=settings.pelican_timeout,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        raise SiteUnavailable from exc
    if resp.status_code == 401:
        raise Unauthenticated
    if resp.status_code != 200:
        raise SiteUnavailable
    try:
        data = resp.json()
    except ValueError as exc:
        raise SiteUnavailable from exc
    if not isinstance(data, dict):
        raise SiteUnavailable
    if data.get("username") is None:
        raise Unauthenticated
    if data.get("id") is None or not data.get("created_at"):
        raise SiteUnavailable
    return Identity(
        f"{data['id']}:{data['created_at']}", str(data["username"]), bool(data.get("is_admin"))
    )
