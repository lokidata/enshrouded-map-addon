# Functional rules (project memory)

Update this file in the same change as any behaviour change.

## What it is
A small service that shows an Enshrouded game server's status (read-only in delivery 1) through a restricted Pelican panel key. It sits behind the Enshrouded map site under `/addon/`. It never handles passwords: it relays the caller's `Cookie` header to the site (`GET /api/v1/auth/me`) to learn who they are, then applies its own access list. It alone holds the Pelican key; the browser never calls Pelican.

## Who sees what
| Who | Status | Journal | Access screen |
| --- | --- | --- | --- |
| Site administrator (`is_admin`) | yes | full (with Pelican status codes) | manages it |
| Level `action` | yes | public columns | no |
| Level `read` | yes | public columns | no |
| None / not listed | refused (403) | refused | refused |
| Not logged in | 401 | 401 | 401 |

`action` is stored and checked now but gives nothing more than `read` until power and backups (delivery 2) exist. The administrator is implicit (always `action`); an empty list means administrator only.

## Screen
One static page (`/addon/`, HTML + vanilla JS, no build): server name, state, CPU, memory, disk, uptime; the journal; for the administrator, the access list with one level selector per site account.

## Access rules
- Identity of a site user = `"<id>:<created_at>"`. Site ids can be reused (plain SQLite primary key), so the pair is used: a re-created account never inherits access.
- If a site account disappears, its entry is removed when the administrator opens the access list (journalled as `removed`). Reinstating is manual: the administrator ticks the new account again.
- The administrator cannot change their own access (400 `administrator_is_implicit`).
- Site unreachable, 5xx or malformed answer on `/auth/me`: 503, never access by default.
- Writes (non-GET) need the header `X-Addon: 1`, and `Origin` equal to `ALLOWED_ORIGIN` when set.

## Journal rules
- Kept 1 day (`JOURNAL_DAYS`), purged at startup and on each journal write.
- Stored: time, username, action (`status`, `access`), target, result, Pelican HTTP status.
- Never stored: file contents, the Pelican key, cookies.
- Non-administrators get only `at, username, action, target, result`.

## Limits
| What | Value |
| --- | --- |
| Pelican calls | GET `/api/client/servers/{id}` and `/resources` only; no redirects |
| Timeout (Pelican and site) | `PELICAN_TIMEOUT`, 10 s |
| Journal retention | 1 day |
| Workers | 1 (one shared SQLite connection) |
| Pelican URL | https only unless `ALLOW_HTTP=true`; trailing `/` stripped |

## API (prefix `/addon/api`)
| Route | Who | Result |
| --- | --- | --- |
| GET `/me` | any logged-in | `username`, `is_admin`, `level` (null = none) |
| GET `/status` | read+ | server status; 502 `pelican_denied` / `pelican_not_found` / `pelican_unavailable` |
| GET `/journal` | read+ | journal rows, newest first |
| GET `/access` | admin | site accounts with their level |
| PUT `/access/{user_key}` | admin | body `{"level": "read"\|"action"\|null}`; null revokes |

Errors: 401 `unauthenticated`, 403 `forbidden`, 503 `site_unavailable`, 404 `unknown_user`.

## Environment
| Variable | Default | Meaning |
| --- | --- | --- |
| `PELICAN_URL` | required | panel base URL |
| `PELICAN_API_KEY` | required | client API key (`pacc_...`), never logged or returned |
| `PELICAN_SERVER_ID` | required | server identifier |
| `SITE_URL` | required | internal URL of the site |
| `DB_PATH` | `/data/addon.db` | SQLite file |
| `JOURNAL_DAYS` | 1 | journal retention |
| `PELICAN_TIMEOUT` | 10 | seconds |
| `ALLOW_HTTP` | false | accept an `http://` panel URL |
| `ALLOWED_ORIGIN` | unset | exact `Origin` required on writes |

## Known gaps
- Refused writes (missing header, wrong origin, 403) are not journalled.
- No JSON line on stdout yet (the audit table only).
- Without `ALLOWED_ORIGIN`, only the `X-Addon` header protects writes: set it.
- Pelican response shapes are written from the docs and unverified against a real panel.
- The Pelican key has no expiry; rotate it by hand.
- Power, backups and the chestsort editor are later deliveries.
