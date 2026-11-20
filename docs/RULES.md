# Functional rules (project memory)

Update this file in the same change as any behaviour change.

## What it is
A small service that shows an Enshrouded game server's status, lets level `action` users start, stop and restart it and create backups, and lists backups, through a restricted Pelican panel key. It sits behind the Enshrouded map site under `/addon/`. It never handles passwords: it relays the caller's `Cookie` header to the site (`GET /api/v1/auth/me`) to learn who they are, then applies its own access list. It alone holds the Pelican key; the browser never calls Pelican.

## Who sees what
Two add-ons, each with its own access list: `server` (status, power, backups, journal) and `chestsort` (the categories editor, only when `CHESTSORT_FILE` is set). The table below is for `server`; `chestsort` follows the same `read` / `action` split on its own routes. A level on one add-on gives nothing on the other.

| Who | Status, backup list | Power, create backup | Journal | Access (site Administration tab) |
| --- | --- | --- | --- | --- |
| Site administrator (`is_admin`) | yes | yes | full (with Pelican status codes) | manages it |
| Level `action` | yes | yes | public columns | no |
| Level `read` | yes | refused (403) | public columns | no |
| None / not listed | refused (403) | refused (403) | refused | refused |
| Not logged in | 401 | 401 | 401 | 401 |

`action` adds `POST /power`, `POST /backups` and `POST /backups/{uuid}/download` to what `read` sees. The administrator is implicit (always `action`); an empty list means administrator only.

## Screen
The screens are **custom elements** that the main site mounts in its own layout, with its own menu and its own "Codex of the Shroud" look; the add-on has no page, header, navigation or design system of its own (`frontend/src/elements.ts`: one Angular application, two elements, built to `main.js` + `styles.css` under `frontend/dist/browser`, served by the API under `/addon/`; no Node in the image). The site reads `GET /addon/api/manifest` (see the API table and `contract/manifest.schema.json`) and adds one tab per add-on the account may use. `GET /addon/` redirects to `/#addon/server` (old bookmarks).

- **`addon-server`** (add-on `server`): section **Pelican** (open by default): state card (name state, CPU, memory, disk, uptime), the Actions card, the backup list; section **Journal** (closed).
- **`addon-chestsort`** (add-on `chestsort`, only when `me.chestsort` is true): section **Les mods du serveur** (open by default): short text on chestsort and storage (only the installed mods are described); section **Catégories de coffres** (closed).

**Attributes set by the site on the element**: `lang` (`fr`, `en`; `de` and anything else fall back to `en`; nothing is stored in the browser) and, on `addon-server`, `active` (`"false"` stops the status poll, any other value reads the state at once and resumes it). An element the user has opened stays mounted when another screen is shown, so an unsaved chestsort draft survives; the confirmation dialog of a hidden element never opens. Dates (`fr-FR` or `en-GB`) and units (Go/Mo or GB/MB, `j` or `d`) follow `lang`. Texts live in `frontend/src/app/core/lang.fr.ts` and `lang.en.ts` (same keys, same `{params}`, checked by a test).

**Style**: the add-on styles are scoped under `[data-addon] addon-server` / `addon-chestsort` (`frontend/src/styles.css`, checked by `scripts/check-scope.mjs`: no rule outside the scope, no hex, no inline style). Buttons, fields, details, `.empty`, `.meta`, `.hint`, `.entries-table`, `.tiles`/`.tile` come from the site's `workshop.css`; see `docs/style-contract.md`. The add-on needs the CSP `default-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` on its own files; the site's CSP (`script-src 'self'`) accepts its script because it is served from the same origin.

Sections are `<details>`; the open state of each is remembered per browser in `localStorage` (when it is unavailable the defaults apply). A missing file or API path is a plain 404 (there is no page fallback).

### Actions card (level `action` and administrator only)
Buttons Start, Stop, Restart start disabled, are enabled from the polled state (Start only when `offline`, Stop and Restart only when `running`), are disabled while the state is unknown (failed or missing `/status` read) and all disabled while a request is in flight. Stop and Restart open a dialog with the checkbox "J'ai prévenu les joueurs"; Confirm stays disabled until it is ticked and then sends `confirm: true`. Start sends no confirmation. Errors show in French, 429 with the wait in seconds. After each action the status, the backup list and (when shown) the journal are reloaded.

### Sauvegardes card
The backup list (name, size, date, status; `en cours` while `completed_at` is null whatever `is_successful` says, `échec` only when `completed_at` is set and `is_successful` is false) for everyone with access; a list load error shows under the button and is cleared by the next successful load. The "Créer une sauvegarde" button (and its result message) is shown to `action` users only; it starts disabled, is enabled once the page has loaded (it depends on the level only) and is disabled while a request is in flight.

### Catégories de coffres card (only when `me.chestsort` is true)
Shown only when `CHESTSORT_FILE` is set. Structured editor: the categories as a row of pills on top (the open one has `aria-pressed`; add, rename, delete under them), then the open category: its items as tiles (picture and name, a remove button in the corner, at most 200 drawn) with a filter box, and its words in a text box above the items (at most 40 rem wide). **Words** stay a text box (one per line; only completely empty lines are dropped, other lines are kept exactly as typed). **Items** are tiles, one per item, with a counter, a filter box (at most 200 chips are drawn, the rest says to narrow the filter) and, for `action`, a remove button per chip and an add box: the game's internal name (for example `Iron_Bar`); several names at once, one per line (Shift+Enter) or separated by commas or semicolons, Enter adds. Names already in the category are reported and skipped; a name over 200 characters or with a control character is refused. **One item, one category**: a name held (ignoring case) by another category is not added; a prompt says where it is and offers \"Déplacer ici\" (one by one, or all) or leaving it; typing 2 letters suggests names already used in other categories (a click proposes that item for the move). A loaded file that already holds an item in two categories shows a red notice listing them, and the server refuses the save until fixed. **Catalogue**: the editor reads the site's `/item-names.json` (`[[internal name, FR, EN, DE, picture guid or ""], ...]`, same origin and session; optional: without it only names already used in other categories are suggested, by internal name). The user never sees internal names when the catalogue knows the item: chips and suggestions show the picture (`/items/<guid>.png`) and the name in the site's language (FR, EN or DE; the internal name is only the tooltip of a chip). In the popup, typing searches the **display name** only (names starting with the text first, up to 8 items not yet in the category, each with the category that holds it); a click adds the item through the same move prompt. With a catalogue and the `action` level, the button "Parcourir les objets…" opens a popup (modal dialog): a search box on the display name or on the name of the category holding the item, one row per item (picture, name, where it is now: "Dans « X »" or "Déjà dans cette catégorie") with "Ajouter" (free item) or "Déplacer ici" (held by another category: the button is the explicit move), at most 100 rows drawn with a counter "N affichés sur M", sorted by name (names starting with the text first); it stays open to add several. The popup is the only way to add items when the catalogue is there (no inline box); without a catalogue the old add box stays (internal names, one per line or comma separated, `Iron_Bar`) with suggestions from the other categories. The category's "Filtrer" box searches the displayed name (internal name for an item the catalogue does not know), not the internal name. Add, rename, delete (delete asks a dialog). "Télécharger le fichier" (every level, read-only included) calls `POST /chestsort/export` with the categories on screen and saves the file a save would write (`_readme` and other keys kept; nothing is written or journalled, 413 over 1 MB). **Refused with 422 and the same error messages as a save while the content has errors** (an item in two categories, for example). Level `read`: read-only view. Level `action`: "Aperçu des changements" calls `/preview` and shows errors, warnings and the diff (an answer that arrives after a further edit is dropped: an edit counter must be unchanged since the request started); "Enregistrer" is enabled only after a preview without error and asks a dialog (checkbox "J'ai relu les changements", sends `confirm: true`); after a save it shows the backup name and that the mod reloads the file in a few seconds. "Restaurer" lists the `.bak-` copies and asks the same dialog; there is no diff preview on a restore. 409 `changed_elsewhere` asks to reload; `rollback_failed` says the file may be damaged and names the `.bak-` copy to restore; every error reason is shown in French.

## Power and backup rules
- Signals: `start`, `stop`, `restart` only (`kill` and anything else: 422 `invalid_request`, never sent). The body is JSON `{"signal": ..., "confirm": ...}`; unparsable JSON, an empty body or an unknown signal is `invalid_request`.
- `stop` and `restart` need `confirm` to be exactly boolean `true` (the string `"true"` or `false` gives 422 `confirmation_required`); the UI checkbox is not the only guard. `start` needs none.
- State precondition, read from Pelican just before acting: `start` only when `offline`, `stop` and `restart` only when `running`; any other state (`starting`, `stopping`, unknown) gives 409 `wrong_state` and nothing is sent.
- Rate limits are global (all users together): one power action per 30 s, one backup creation per 300 s. Over the limit: 429, header `Retry-After` and body `{"detail": "rate_limited", "retry_after": <s>}`. A Pelican call that succeeded or may have been applied (2xx, `pelican_unavailable`: timeout, 5xx, redirect; `pelican_timeout`) starts a window; a refused one (`pelican_denied`, `pelican_not_found`, `pelican_rejected`) or a refusal before the call (`wrong_state`, `confirmation_required`, `invalid_request`, `busy`) does not.
- One lock serialises power and backup creation: a double click or two users at once send one Pelican call, the second sees the new state or window. A request waits at most 5 s for the lock (then 409 `busy`); the locked section (status read and Pelican call) is bounded to 25 s (then 504 `pelican_timeout`, the window starts since the outcome is unknown); the lock is always released.
- Order of checks: level (403), body validity, confirmation, then under the lock state, rate limit, Pelican call.
- Pelican refusals: 403 -> 502 `pelican_denied`, 404 -> 502 `pelican_not_found`, 5xx, timeout, redirect or unexpected shape -> 502 `pelican_unavailable`, 400/409/422 on a POST -> 409 `pelican_rejected` (e.g. backup limit reached; Pelican's reason goes to the container log only, not to the response). 400/409/422 on a GET (status, backup list, the status read before a power action) -> 502 `pelican_unavailable`. Any 2xx from Pelican on a POST counts as success.
- Download: `POST /backups/{uuid}/download` (level `action`, `X-Addon` guard; `uuid` must be a UUID, else 404/422 and nothing sent) reads the backup from Pelican, refuses with 409 `backup_not_ready` unless `completed_at` is set and `is_successful` is true, then asks Pelican for a one-time signed URL and returns `{"url"}` (http/https only, else 502). The URL is a credential: never logged, never journalled (journal: action `backup`, target `download:<uuid>`). No lock (read-only on the panel); one request per 5 s for everyone (429). Pelican refusals are 502 like elsewhere. The page shows a "Télécharger" button per finished backup (`action` only) and navigates to the URL; the browser must reach the node (Wings) address. Delete, restore and lock stay out of the add-on.
- An unexpected error inside `POST /power` or `POST /backups` is journalled `internal_error` and answers 500 `internal_error` (traceback in the container log).
- Success: `POST /power` returns `{"signal", "result": "ok"}`; `POST /backups` returns the created backup (`uuid`, `name`, `bytes`, `created_at`, `completed_at`, `is_successful`, `is_locked`), or `{"backup": null}` when Pelican answered 2xx with a body that cannot be parsed (logged `bad_response`; still a success: journalled `ok`, window started).
- Not offered: backup restore, delete, download or lock; `kill`.

## Chestsort editor rules
- Off unless `CHESTSORT_FILE` is set: every `/chestsort` route is 404 and `GET /me` has `chestsort: false`. The path comes from the setting only, never from a request. It must start with `/`, not end with `/`, no `..`, no `\`, no control character, at most 200 characters (else the start fails).
- Levels: `read` may use `GET /chestsort` and `GET /chestsort/backups`; `action` also `POST /chestsort/preview`, `PUT /chestsort`, `POST /chestsort/restore`. Others 403.
- Only `categories` is edited. The rest of the file (`_readme` and any other key) is kept in its order; `other_keys_kept` tells the page there are such keys.
- Validation (errors refuse the save; the messages are in French): `categories` an object of 1 to 200 categories; name 1 to 60 characters without control characters, unique ignoring case; each category an object with exactly `words` and `items` (unknown or missing key refused); each a list of non-empty strings of at most 200 characters without control characters; a name, word or item that cannot be written as UTF-8 (a lone surrogate such as `"\ud800"`) is refused with a message naming the category (an invalid name or unknown key is shown with `?` in its place); `words` at most 100, `items` at most 20000; `_readme` (if present) a list of strings. **An item may be in one category only**: the same item (compared ignoring case) in two categories is an error naming both (at most 20 messages, then `... et N autres objets en double.`); the same item twice in one category is allowed. Warnings (do not block): a name equal to a built-in group (`nourriture`), an empty `items`, a word in two categories.
- Canonical dump: `json.dumps(ensure_ascii=False, indent=2)`, no trailing newline (the mod writes none, so a save shows no spurious diff). Hash = SHA-256 of the file text. File and request bodies are limited to 1 MB (body: 413 `too_large` while streaming; file: 413 too, but `GET` reads the whole file before the size check). A body nested too deeply to parse is 422 `invalid_request`. The file is decoded as strict UTF-8 (never lossily): otherwise 422 `file_not_utf8` on `GET`, preview, save and restore (a restore also for the chosen copy), nothing written; CRLF and a BOM are kept as they are (a BOM makes the parse fail: 502 `file_invalid`).
- `POST /preview` is not journalled and takes no lock; one preview per second for everyone (else 429 `rate_limited` with `Retry-After`, like the other windows); the diff is computed in a worker thread.
- Save pipeline, under the shared action lock and a 10 s window shared by save and restore: read the file; its hash must equal `base_hash` (else 409 `changed_elsewhere`, nothing written); list the folder and write a copy `<file>.bak-YYYYMMDD-HHMMSS` (UTC), or `...-HHMMSS-2`, `-3`... when that name already exists (same second, clock stepped back): an existing copy is never overwritten; read it back (mismatch or failed read: 502 `backup_failed`, the new content is never written); write the new content and read it back. A definitive refusal of that write (Pelican 403, 404, 422: 502 `pelican_denied` / `pelican_not_found`, 409 `pelican_rejected`) means nothing was applied: no rollback, no window. Any other failure once the write was attempted (5xx or unreachable during the write, any read-back error, a mismatch) writes the old content back and verifies it: 502 `verify_failed` (journalled `rolled_back`), or 502 `rollback_failed` with `{"detail", "backup"}` (the `.bak-` name to restore from) when the rollback write or its check fails. The window starts whenever the new write was attempted and not definitively refused.
- `PUT` needs `confirm` exactly `true` (else 422 `confirmation_required`) and no validation error (422 `invalid_content` with `errors`). `POST /restore` needs `confirm: true`, a name that matches `.bak-YYYYMMDD-HHMMSS` or `.bak-YYYYMMDD-HHMMSS-N` of the configured file (else 422 `invalid_backup_name`) and present in the folder listing (else 404 `unknown_backup`); the copy is validated like a save (422 `invalid_content`) and restored byte for byte, after the same backup of the current file, `base_hash` and verify steps. A restore is a new save: the copy it replaces is itself backed up.
- `GET /chestsort/backups`: the 20 newest names, newest first (by name).
- Shared lock: waits at most 5 s (409 `busy`), the locked section is bounded to 25 s (504 `pelican_timeout`, window started). When the 25 s fire after the new write was attempted, the old content is written back and checked with a fresh 10 s budget, still under the lock: 504 `pelican_timeout` journalled `timeout_rolled_back`, or 502 `rollback_failed` (with `backup`) journalled `timeout` if that failed; inside the 10 s window 429 `rate_limited` with `Retry-After`. The file being invalid JSON: 502 `file_invalid`; Pelican failures 502 `pelican_denied` / `pelican_not_found` / `pelican_unavailable`.
- Journal: action `chestsort`, target `save` or `restore`, result `ok` or the refusal reason (`confirmation_required`, `invalid_request`, `invalid_content`, `invalid_backup_name`, `unknown_backup`, `changed_elsewhere`, `too_large`, `file_invalid`, `file_not_utf8`, `backup_failed`, `rolled_back`, `rollback_failed`, `rate_limited`, `busy`, `timeout`, `timeout_rolled_back`, `pelican_*`, `internal_error`). Never the content, the diff or the validation messages. The log has one line on success (`chestsort_written categories= items= bak=`), counts and the backup name only. Previews and reads are not journalled.

## Access rules
- The lists are managed from the **site's Administration dialog**, one tab per add-on, through `GET /{addon}/access` and `PUT /{addon}/access/{user_key}` (administrator only); the add-on's own screens have no access section.
- One list per add-on, table `access_v2(addon, user_key, username, level, by, at)`. The former single `access` table is neither read nor migrated: both lists start empty after the upgrade and the administrator grants access again.
- `GET /me` returns `levels: {server, chestsort}` (null = none; the administrator is `action` on both).
- Identity of a site user = `"<id>:<created_at>"`. Site ids can be reused (plain SQLite primary key), so the pair is used: a re-created account never inherits access.
- If a site account disappears, its entry is removed when the administrator opens the access list (journalled as `removed`). Reinstating is manual: the administrator ticks the new account again.
- The administrator cannot change their own access (400 `administrator_is_implicit`).
- Site unreachable, 5xx or malformed answer on `/auth/me`: 503, never access by default.
- Writes (non-GET) need the header `X-Addon: 1`, and `Origin` equal to `ALLOWED_ORIGIN` when set.

## Journal rules
- Kept 1 day (`JOURNAL_DAYS`), purged at startup and on each journal write.
- Pelican failures are written to the container log (stderr), one warning line per distinct reason and minute: `pelican_error kind=<denied|not_found|rejected|unreachable|unavailable|bad_response> status=<http> detail='...'`. `detail` is Pelican's own explanation when it gives one (a `denied` caused by the key's IP restriction shows the refused address), cut to 200 characters on one line; never the key or the request headers.
- Stored: time, username, action, target, result, Pelican HTTP status.
  - `access`: target = `<addon>:<account>`, result = the level, `revoked` or `removed`.
  - `power`: target = the signal (`start`, `stop`, `restart`), or `invalid` when the body had no usable signal; result = `ok` or the refusal reason: `invalid_request`, `confirmation_required`, `wrong_state`, `rate_limited`, `busy`, `timeout` (answered 504 `pelican_timeout`), `pelican_denied`, `pelican_not_found`, `pelican_unavailable`, `pelican_rejected`, `internal_error`.
  - `backup`: target = `create`; result as above (without the signal-related reasons).
  - The Pelican status column is filled only for `pelican_denied` (403), `pelican_not_found` (404) and `pelican_rejected` (400/409/422 on a POST); empty for `ok`, refusals before the call and every `pelican_unavailable` (5xx, redirect, timeout, bad shape, 400/409/422 on a GET).
  - Every attempt by an `action` user that reaches the route is journalled, refused or not. A 403 for a `read` or unlisted user (and a missing `X-Addon` header or wrong origin) is not journalled.
  - Status polls (GET `/status`) and backup list reads are not journalled (a poll per viewer would fill it).
- Never stored: file contents, the Pelican key, cookies.
- Non-administrators get only `at, username, action, target, result`.

## Limits
| What | Value |
| --- | --- |
| Pelican calls | GET `/api/client/servers/{id}`, `/resources`, `/backups`, `/files/contents?file=`, `/files/list?directory=`; POST `/power`, `/backups`, `/files/write?file=` (raw body, answer 204; verified against the panel); no redirects |
| Chestsort | 10 s window (save and restore together), 1 MB, 20 copies listed |
| Power rate limit | 1 per 30 s, global, in memory |
| Backup creation rate limit | 1 per 300 s, global, in memory |
| Timeout (Pelican and site) | `PELICAN_TIMEOUT`, 10 s |
| Action lock | wait 5 s (`busy`), locked section 25 s (`pelican_timeout`) |
| Journal retention | 1 day |
| Workers | 1 (one shared SQLite connection) |
| Pelican URL | https only unless `ALLOW_HTTP=true`; trailing `/` stripped |

## API (prefix `/addon/api`)
| Route | Who | Result |
| --- | --- | --- |
| GET `/me` | any logged-in | `username`, `is_admin`, `levels` (`{server, chestsort}`, null = none), `backup_filtered`, `chestsort` |
| GET `/manifest` | any logged-in | `{api_version: 1, script, styles, addons: [{id, version, level, name{fr,en}, element}]}` filtered by the caller's levels (`[]` when none; `chestsort` only when on); `Cache-Control: no-cache`; schema in `contract/manifest.schema.json` |
| GET `/status` | read+ | server status; 502 `pelican_denied` / `pelican_not_found` / `pelican_unavailable` |
| POST `/power` | action | body `{"signal": "start"\|"stop"\|"restart", "confirm": true}` (`confirm` required for stop and restart); `{"signal", "result": "ok"}` |
| GET `/backups` | read+ | list of backups (`uuid`, `name`, `bytes`, `created_at`, `completed_at`, `is_successful`, `is_locked`); 502 as `/status` |
| POST `/backups` | action | body `{}`; the created backup or `{"backup": null}`; 409 `pelican_rejected` when Pelican refuses (e.g. limit) |
| GET `/chestsort` | read+ | `{categories, other_keys_kept, hash, bytes}`; 404 when off |
| POST `/chestsort/preview` | action | body `{categories}`; `{errors, warnings, diff, changed}`, writes nothing; one per second (429) |
| PUT `/chestsort` | action | body `{categories, base_hash, confirm: true}`; `{backup, hash}`; 502 `rollback_failed` adds `backup` |
| GET `/chestsort/backups` | read+ | the 20 newest `.bak-` names |
| POST `/chestsort/restore` | action | body `{name, base_hash, confirm: true}`; `{backup, hash}` |
| GET `/journal` | read+ | the 500 newest journal rows, newest first |
| GET `/{addon}/access` | admin | site accounts with their level on `server` or `chestsort`; 404 for another name or `chestsort` when off |
| PUT `/{addon}/access/{user_key}` | admin | body `{"level": "read"\|"action"\|null}`; null revokes |

Errors: 401 `unauthenticated`, 403 `forbidden`, 503 `site_unavailable`, 404 `unknown_user`; on the action routes also 422 `invalid_request` / `confirmation_required`, 409 `wrong_state` / `pelican_rejected` / `busy`, 429 `rate_limited` (with `Retry-After`), 502 `pelican_denied` / `pelican_not_found` / `pelican_unavailable`, 504 `pelican_timeout`, 500 `internal_error`.

## Environment
| Variable | Default | Meaning |
| --- | --- | --- |
| `PELICAN_URL` | required | panel base URL |
| `PELICAN_API_KEY` | required | client API key (`pacc_...`), never logged or returned |
| `PELICAN_SERVER_ID` | required | server identifier |
| `SITE_URL` | required | internal URL of the site |
| `DB_PATH` | `/data/addon.db` | SQLite file |
| `JOURNAL_DAYS` | 1 | journal retention |
| `STATIC_DIR` | `frontend/dist/browser` next to `src/` | folder of the built UI (set in dev only; the image has it in place) |
| `PELICAN_TIMEOUT` | 10 | seconds |
| `ALLOW_HTTP` | false | accept an `http://` panel URL |
| `ALLOWED_ORIGIN` | unset | exact `Origin` required on writes; must look like `https://host[:port]` (scheme, no path; a trailing `/` is stripped; anything else stops the start). A refused write logs `write_refused reason=missing_header\|origin_mismatch` (never the received value) |
| `CHESTSORT_FILE` | unset (feature off) | path of the mod's categories file from the server root, e.g. `/chestsort_categories.json`; the editor reads and writes it, and its `.bak-` copies next to it |
| `BACKUP_IGNORED` | unset (then every backup asks for a confirmation, see below) | Pelican ignore list for backups (gitignore style, one pattern per line; `\n` accepted in a one-line variable). Example keeping only the save: `/*\n!/savegame/\n!/savegame/**`. Empty = Pelican's default (everything). Sent as `ignored` (confirmed by the panel's own OpenAPI export: newline separated list, `.gitignore` format) |

## Known gaps
- Refused writes (missing header, wrong origin, 403) are not journalled.
- No JSON line on stdout for access changes yet (the audit table only).
- Without `ALLOWED_ORIGIN`, only the `X-Addon` header protects writes: set it.
- Backup without `BACKUP_IGNORED`: Pelican would archive every file of the server (tens of GB). `POST /backups` then needs `confirm_full: true` in the body (strictly `true`), else 422 `full_backup_confirmation_required` (journalled, nothing sent to Pelican); the page asks with a dialog ("Sauvegarder tout le serveur ?"). `GET /me` returns `backup_filtered` (true when `BACKUP_IGNORED` is set; then no confirmation is asked).
- Pelican response shapes: power (204), backup creation (200, `attributes` with `uuid`, `is_successful`, `is_locked`, `name`, `bytes`, `created_at`, `completed_at`) and the `ignored` field were checked against the panel's OpenAPI export of 2026-11-14 (client API), and the status and backup list worked on the real panel; power and backup creation on the real server are still to be tried by the maintainer. Parsing stays defensive and an unexpected shape is `PelicanUnavailable`. The backup list is paginated by Pelican (`meta.pagination`); only the first page is read (no page parameter is documented), so a server with many backups may not show the newest ones.
- Any 2xx from Pelican on power or backup creation counts as success; the real server state is only seen at the next poll.
- Refused writes of delivery 1 (missing header, wrong origin, 403) are still not journalled.
- Rate limits and the lock are in memory: they reset on restart and assume one worker.
- No backup restore, delete, download or lock.
- The Pelican key has no expiry; rotate it by hand.
- Chestsort: the write is not atomic (Pelican writes in place). A failed rollback leaves the file possibly damaged; the `.bak-` copy remains and the page names it (`rollback_failed`). A rollback cut by its 10 s budget may still land later on the panel side.
- Chestsort: backups are sorted by name, so `-10` lists before `-9` within the same second.
- Chestsort: `.bak-` copies accumulate (the key has no `file.delete`); clean them in the panel's file manager. Only the 20 newest are listed.
- Chestsort: the mod reports its own parse errors only in `shroudlink.log`; the page does not show them.
- Chestsort: `GET` reads the whole file before the 1 MB check; a restore has no diff preview.

## JSON safety
- Every JSON body and the chestsort file are read with `addon/jsonsafe.py`: the nesting depth is measured first (iteratively, strings skipped) and a document deeper than 40 levels is refused (422 `invalid_request`, or a French error for the file) before `json.loads` runs. Reason: `json.loads` on tens of thousands of nested brackets overflows the C stack and kills the whole process on some Python versions and stack sizes (found when the CI crashed on Python 3.15).
- The optional bodies of `POST /power` and `POST /backups` are also limited to 1 MB (413 `too_large`, journalled).

