"""Who is the caller? Relay the site session cookie to the site, never handle passwords."""

from dataclasses import dataclass

import httpx

from addon.config import Settings
from addon.store import Level


class Unauthenticated(Exception):
    pass


class SiteUnavailable(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    key: str  # the site's `user_key`
    username: str
    is_admin: bool
    level: Level | None  # this entry's level; None = the site answered 403 (no access)


async def who_am_i(
    cookie_header: str | None, client: httpx.AsyncClient, settings: Settings, entry: str
) -> Identity:
    if not cookie_header:
        raise Unauthenticated
    url = f"{settings.site_url.rstrip('/')}/api/v1/addons/{entry}/me"
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
    if resp.status_code == 403:
        # the site never says why (unknown or disabled entry, or no level): no access, no identity
        return Identity("", "", False, None)
    if resp.status_code != 200:
        raise SiteUnavailable
    try:
        data = resp.json()
    except ValueError as exc:
        raise SiteUnavailable from exc
    if not isinstance(data, dict):
        raise SiteUnavailable
    key, name, level = data.get("user_key"), data.get("username"), data.get("level")
    if not isinstance(key, str) or not key or not isinstance(name, str) or not name:
        raise SiteUnavailable
    if level not in ("read", "action", None):
        raise SiteUnavailable
    return Identity(key, name, data.get("is_admin") is True, level)
