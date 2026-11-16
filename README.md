# enshrouded-map-addon

Game-server add-on for the private [Enshrouded interactive map](https://github.com/lokidata/enshrouded-map) site: shows the server status, lets authorised users start, stop and restart it and create backups (stop and restart need a confirmation; rate-limited), and lists backups, through a restricted Pelican key, with a per-user access list and a 1-day audit journal (access changes and every power or backup attempt, 500 newest rows shown; status polls are not journalled) (FastAPI, Python 3.13). Functional rules: `docs/RULES.md`.

## How it plugs into the site
Run it as its own container and set `ADDON_URL` (origin only, e.g. `http://addon:8000`) on the site's web container. The site's nginx then proxies `/addon/` to it. For each request the add-on relays the caller's cookie to the site's `/api/v1/auth/me` (and `/api/v1/auth/users` for the administrator's access screen), so it needs the companion site change (`id`, `created_at` and `addon` in `/auth/me`). Without it the add-on refuses everyone. See `deploy/`.

## Pelican prerequisites
- A dedicated Pelican user with **no role** (a role with admin "update" on servers would give all rights on all servers).
- Add it to the game server as a sub-user with only: `control.start`, `control.stop`, `control.restart`, `file.read`, `file.read-content`, `file.create`, `backup.create`, `backup.read`. The `control.*` and `backup.*` permissions are used by the power and backup actions; `file.read`, `file.read-content` and `file.create` are used by the chestsort editor (read the file, list its folder, write the file and its `.bak-` copies; `file.create` is what the panel asks for `files/write`); nothing deletes a file, so clean old `.bak-` copies by hand in the panel's file manager.
- Create an API key for that user with **allowed IPs = the address Pelican sees** (the denial message shows it). The secret is shown once.
- `PELICAN_URL` may end with `/` (it is stripped; a double slash gives a 404).
- Network: from the LAN the panel's public name may resolve to the public IP and time out (hairpin NAT). Fix it with a local DNS record to your reverse proxy, or `extra_hosts` in the compose file.

## Run
```bash
make check   # ruff, mypy, bandit, pip-audit, pytest
make check-frontend   # npm audit, lint (+ design guard), build, Vitest, Playwright + AXE
make lock    # regenerate requirements.lock after a dependency change
```
The UI is an Angular app in `frontend/` (Node 24 to build; `cd frontend && npm ci --ignore-scripts && npm run build`, then run the API with `STATIC_DIR` unset: it serves `frontend/dist/browser`). Environment variables: `docs/RULES.md`. Container: `Dockerfile`, example stack in `deploy/`.

## Security notes
- Pelican failures are logged with their reason (and the refused IP address when Pelican says it); the key is read from the environment only, never logged or returned; the browser never calls Pelican.
- Set `ALLOWED_ORIGIN` to the site's origin with its scheme, e.g. `https://carte.example.lan` (no path; a missing scheme stops the start): otherwise only the `X-Addon` header protects writes.
- Read-only rootfs, non-root, no capabilities; the only writable place is `/data`.
- Report vulnerabilities: `SECURITY.md`.

MIT licence, see `LICENSE`.

## Chestsort editor (optional)
Set `CHESTSORT_FILE` to the mod's categories file from the server root (e.g. `/chestsort_categories.json`) to show the "Catégories de coffres" card: view for level `read`, edit and restore for `action`, with validation, a diff (one preview per second), a dated `.bak-` copy before each write (never overwriting an existing one: `-2`, `-3`... suffix), a read-back check and a rollback on any failure after the write was sent (also after a timeout); a failed rollback answers `rollback_failed` with the `.bak-` name to restore. A file that is not UTF-8 is refused (`file_not_utf8`), never rewritten. Off when unset. Rules: `docs/RULES.md`. The write is `POST files/write?file=<path>` with the raw body (204).

## Backups of the save only

By default Pelican backs up every file of the server. Set `BACKUP_IGNORED` (gitignore style; `\n` separates patterns in a one-line variable) to keep only the save folder:

```
BACKUP_IGNORED=/*\n!/savegame/\n!/savegame/**
```
