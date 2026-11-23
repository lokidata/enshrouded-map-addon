# enshrouded-map-addon

Game-server add-ons for the private [Enshrouded interactive map](https://github.com/lokidata/enshrouded-map) site (the server page and the chestsort categories editor): shows the server status, lets authorised users start, stop and restart it and create backups (stop and restart need a confirmation; rate-limited), and lists backups, through a restricted Pelican key, with levels granted by the site and a 1-day audit journal (every power or backup attempt, 500 newest rows shown; status polls are not journalled) (FastAPI, Python 3.13). Functional rules: `docs/RULES.md`.

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
## How it plugs into the site
Run it as its own container and set `ADDON_URL` (origin only, e.g. `http://addon:8000`) on the site's web **and** api containers (the API reads the manifests). The site's nginx then proxies `/addon/<key>/` (for example `/addon/main/`) to it. `ADDON_URL` (or `ADDONS=<key>=<origin>,...`) is a **site-side** setting: the site gives the add-on a key, and the add-on never knows it (its paths are relative, the site serves it under `/addon/<key>/`). See `deploy/`.

For each request the add-on relays the caller's cookie to the site's `GET /api/v1/addons/<entry>/me`, which answers who the caller is and their level on that entry (`read`, `action` or none). The site keeps the access lists: in the site's Administration dialog, enable each entry, then grant access per account. The add-on has no list of its own and no access routes.

The screens are two custom elements (`addon-server`, `addon-chestsort`) that the site mounts in its own layout: the site reads the public `GET /addon/api/manifest` (api_version 2, contract in `contract/manifest.schema.json`), adds one tab per enabled entry the account may use and loads `main.js` + `styles.css` from `/addon/<key>/`. Elements receive the attributes `lang`, `active` and `base` (the public path, derived from the bundle URL when unset). `GET /addon/` redirects to `/#addon/server`. Ship the site and the add-on together: the add-on needs the site's `/api/v1/addons` routes, and after the upgrade every access list starts empty, so enable the entries and grant access again (the old `access` table is not migrated; `access_v2` is dormant).

The UI is an Angular app in `frontend/` (Node 24 to build; `cd frontend && npm ci --ignore-scripts && npm run build`, then run the API with `STATIC_DIR` unset: it serves `frontend/dist/browser`; a bare element needs the site's tokens and `workshop.css` to look right, so try it through the site). Environment variables: `docs/RULES.md`. Container: `Dockerfile`, example stack in `deploy/`.

## Security notes
- Pelican failures are logged with their reason (and the refused IP address when Pelican says it); the key is read from the environment only, never logged or returned; the browser never calls Pelican.
- Set `ALLOWED_ORIGIN` to the site's origin with its scheme, e.g. `https://carte.example.lan` (no path; a missing scheme stops the start): otherwise only the `X-Addon` header protects writes.
- Read-only rootfs, non-root, no capabilities; the only writable place is `/data`.
- Report vulnerabilities: `SECURITY.md`.

MIT licence, see `LICENSE`.

## Chestsort editor (optional)
Set `CHESTSORT_FILE` to the mod's categories file from the server root (e.g. `/chestsort_categories.json`) to show the "Catégories de coffres" card: view for level `read`, edit and restore for `action`, with validation, a diff (one preview per second), a dated `.bak-` copy before each write (never overwriting an existing one: `-2`, `-3`... suffix), a read-back check and a rollback on any failure after the write was sent (also after a timeout); a failed rollback answers `rollback_failed` with the `.bak-` name to restore. A file that is not UTF-8 is refused (`file_not_utf8`), never rewritten. Off when unset. The editor shows the game's items with their picture and name in the site's language when the site serves `/item-names.json` (optional), can download the file it would write, and refuses an item in two categories. Rules: `docs/RULES.md`. The write is `POST files/write?file=<path>` with the raw body (204).

## Backups of the save only

By default Pelican backs up every file of the server. Set `BACKUP_IGNORED` (gitignore style; `\n` separates patterns in a one-line variable) to keep only the save folder:

```
BACKUP_IGNORED=/*\n!/savegame/\n!/savegame/**
```
