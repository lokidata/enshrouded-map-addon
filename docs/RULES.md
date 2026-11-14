# Functional rules (project memory)

Update this file in the same change as any behaviour change.

## What it is
A small service that shows an Enshrouded game server's status, lets level `action` users start, stop and restart it and create backups, and lists backups, through a restricted Pelican panel key. It sits behind the Enshrouded map site under `/addon/`. It never handles passwords: it relays the caller's `Cookie` header to the site (`GET /api/v1/auth/me`) to learn who they are, then applies its own access list. It alone holds the Pelican key; the browser never calls Pelican.

## Who sees what
| Who | Status, backup list | Power, create backup | Journal | Access screen |
| --- | --- | --- | --- | --- |
| Site administrator (`is_admin`) | yes | yes | full (with Pelican status codes) | manages it |
| Level `action` | yes | yes | public columns | no |
| Level `read` | yes | refused (403) | public columns | no |
| None / not listed | refused (403) | refused (403) | refused | refused |
| Not logged in | 401 | 401 | 401 | 401 |

`action` adds `POST /power` and `POST /backups` to what `read` sees. The administrator is implicit (always `action`); an empty list means administrator only.

## Screen
One static page (`/addon/`, HTML + vanilla JS, no build): server name, state, CPU, memory, disk, uptime; two cards for `action` users (below); the backup list (everyone with access); the journal; for the administrator, the access list with one level selector per site account.

### Actions card (level `action` and administrator only)
Buttons Start, Stop, Restart, enabled from the polled state (Start only when `offline`, Stop and Restart only when `running`) and all disabled while a request is in flight. Stop and Restart open a dialog with the checkbox "J'ai prévenu les joueurs"; Confirm stays disabled until it is ticked and then sends `confirm: true`. Start sends no confirmation. Errors show in French, 429 with the wait in seconds.

### Sauvegardes card
The backup list (name, size, date, status; `en cours` while `is_successful` is null, `échec` when false) for everyone with access. The "Créer une sauvegarde" button (and its result message) is shown to `action` users only.

## Power and backup rules
- Signals: `start`, `stop`, `restart` only (`kill` and anything else: 422 `invalid_request`, never sent). The body is JSON `{"signal": ..., "confirm": ...}`; unparsable JSON, an empty body or an unknown signal is `invalid_request`.
- `stop` and `restart` need `confirm` to be exactly boolean `true` (the string `"true"` or `false` gives 422 `confirmation_required`); the UI checkbox is not the only guard. `start` needs none.
- State precondition, read from Pelican just before acting: `start` only when `offline`, `stop` and `restart` only when `running`; any other state (`starting`, `stopping`, unknown) gives 409 `wrong_state` and nothing is sent.
- Rate limits are global (all users together): one power action per 30 s, one backup creation per 300 s. Over the limit: 429, header `Retry-After` and body `{"detail": "rate_limited", "retry_after": <s>}`. Only a successful Pelican call starts a window; a failed one does not.
- One lock serialises power and backup creation: a double click or two users at once send one Pelican call, the second sees the new state or window.
- Order of checks: level (403), body validity, confirmation, then under the lock state, rate limit, Pelican call.
- Pelican refusals: 403 -> 502 `pelican_denied`, 404 -> 502 `pelican_not_found`, 5xx, timeout, redirect or unexpected shape -> 502 `pelican_unavailable`, 400/409/422 -> 409 `pelican_rejected` (e.g. backup limit reached; Pelican's reason goes to the container log only, not to the response). Any 2xx from Pelican counts as success.
- Success: `POST /power` returns `{"signal", "result": "ok"}`; `POST /backups` returns the created backup (`uuid`, `name`, `bytes`, `created_at`, `completed_at`, `is_successful`, `is_locked`).
- Not offered: backup restore, delete, download or lock; `kill`.

## Access rules
- Identity of a site user = `"<id>:<created_at>"`. Site ids can be reused (plain SQLite primary key), so the pair is used: a re-created account never inherits access.
- If a site account disappears, its entry is removed when the administrator opens the access list (journalled as `removed`). Reinstating is manual: the administrator ticks the new account again.
- The administrator cannot change their own access (400 `administrator_is_implicit`).
- Site unreachable, 5xx or malformed answer on `/auth/me`: 503, never access by default.
- Writes (non-GET) need the header `X-Addon: 1`, and `Origin` equal to `ALLOWED_ORIGIN` when set.

## Journal rules
- Kept 1 day (`JOURNAL_DAYS`), purged at startup and on each journal write.
- Pelican failures are written to the container log (stderr), one warning line per distinct reason and minute: `pelican_error kind=<denied|not_found|unreachable|unavailable|bad_response> status=<http> detail='...'`. `detail` is Pelican's own explanation when it gives one (a `denied` caused by the key's IP restriction shows the refused address), cut to 200 characters on one line; never the key or the request headers.
- Stored: time, username, action, target, result, Pelican HTTP status.
  - `access`: target = the account, result = the level, `revoked` or `removed`.
  - `power`: target = the signal (`start`, `stop`, `restart`), or `invalid` when the body had no usable signal; result = `ok` or the refusal reason: `invalid_request`, `confirmation_required`, `wrong_state`, `rate_limited`, `pelican_denied`, `pelican_not_found`, `pelican_unavailable`, `pelican_rejected`.
  - `backup`: target = `create`; result as above (without the signal-related reasons).
  - The Pelican status column is filled only when Pelican answered with a refusal code (403, 404, 400/409/422, other non-2xx); empty for `ok`, refusals before the call and unreachable panel.
  - Every attempt by an `action` user that reaches the route is journalled, refused or not. A 403 for a `read` or unlisted user (and a missing `X-Addon` header or wrong origin) is not journalled.
  - Status polls (GET `/status`) and backup list reads are not journalled (a poll per viewer would fill it).
- Never stored: file contents, the Pelican key, cookies.
- Non-administrators get only `at, username, action, target, result`.

## Limits
| What | Value |
| --- | --- |
| Pelican calls | GET `/api/client/servers/{id}`, `/resources`, `/backups`; POST `/power`, `/backups`; no redirects |
| Power rate limit | 1 per 30 s, global, in memory |
| Backup creation rate limit | 1 per 300 s, global, in memory |
| Timeout (Pelican and site) | `PELICAN_TIMEOUT`, 10 s |
| Journal retention | 1 day |
| Workers | 1 (one shared SQLite connection) |
| Pelican URL | https only unless `ALLOW_HTTP=true`; trailing `/` stripped |

## API (prefix `/addon/api`)
| Route | Who | Result |
| --- | --- | --- |
| GET `/me` | any logged-in | `username`, `is_admin`, `level` (null = none) |
| GET `/status` | read+ | server status; 502 `pelican_denied` / `pelican_not_found` / `pelican_unavailable` |
| POST `/power` | action | body `{"signal": "start"\|"stop"\|"restart", "confirm": true}` (`confirm` required for stop and restart); `{"signal", "result": "ok"}` |
| GET `/backups` | read+ | list of backups (`uuid`, `name`, `bytes`, `created_at`, `completed_at`, `is_successful`, `is_locked`); 502 as `/status` |
| POST `/backups` | action | body `{}`; the created backup; 409 `pelican_rejected` when Pelican refuses (e.g. limit) |
| GET `/journal` | read+ | the 500 newest journal rows, newest first |
| GET `/access` | admin | site accounts with their level |
| PUT `/access/{user_key}` | admin | body `{"level": "read"\|"action"\|null}`; null revokes |

Errors: 401 `unauthenticated`, 403 `forbidden`, 503 `site_unavailable`, 404 `unknown_user`; on the action routes also 422 `invalid_request` / `confirmation_required`, 409 `wrong_state` / `pelican_rejected`, 429 `rate_limited` (with `Retry-After`), 502 `pelican_denied` / `pelican_not_found` / `pelican_unavailable`.

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
| `ALLOWED_ORIGIN` | unset | exact `Origin` required on writes (trailing `/` stripped) |

## Known gaps
- Refused writes (missing header, wrong origin, 403) are not journalled.
- No JSON line on stdout for access changes yet (the audit table only).
- Without `ALLOWED_ORIGIN`, only the `X-Addon` header protects writes: set it.
- Pelican response shapes (status, resources, and now power and backup creation/list) are written from the docs and unverified against a real panel; parsing is defensive and an unexpected shape is `pelican_unavailable`.
- Any 2xx from Pelican on power or backup creation counts as success; the real server state is only seen at the next poll.
- Refused writes of delivery 1 (missing header, wrong origin, 403) are still not journalled.
- Rate limits and the lock are in memory: they reset on restart and assume one worker.
- No backup restore, delete, download or lock.
- The Pelican key has no expiry; rotate it by hand.
- The chestsort editor is delivery 3.
