# enshrouded-map-addon

Game-server add-on for the private [Enshrouded interactive map](https://github.com/lokidata/enshrouded-map) site: shows the server status through a restricted Pelican key, with a per-user access list and a 1-day audit journal (access changes only, 500 newest rows shown; status polls are not journalled) (FastAPI, Python 3.13). Functional rules: `docs/RULES.md`.

## How it plugs into the site
Run it as its own container and set `ADDON_URL` (origin only, e.g. `http://addon:8000`) on the site's web container. The site's nginx then proxies `/addon/` to it. For each request the add-on relays the caller's cookie to the site's `/api/v1/auth/me` (and `/api/v1/auth/users` for the administrator's access screen), so it needs the companion site change (`id`, `created_at` and `addon` in `/auth/me`). Without it the add-on refuses everyone. See `deploy/`.

## Pelican prerequisites
- A dedicated Pelican user with **no role** (a role with admin "update" on servers would give all rights on all servers).
- Add it to the game server as a sub-user with only: `control.start`, `control.stop`, `control.restart`, `file.read`, `file.read-content`, `file.create`, `file.update`, `backup.create`, `backup.read`.
- Create an API key for that user with **allowed IPs = the address Pelican sees** (the denial message shows it). The secret is shown once.
- `PELICAN_URL` may end with `/` (it is stripped; a double slash gives a 404).
- Network: from the LAN the panel's public name may resolve to the public IP and time out (hairpin NAT). Fix it with a local DNS record to your reverse proxy, or `extra_hosts` in the compose file.

## Run
```bash
make check   # ruff, mypy, bandit, pip-audit, pytest
make lock    # regenerate requirements.lock after a dependency change
```
Environment variables: `docs/RULES.md`. Container: `Dockerfile`, example stack in `deploy/`.

## Security notes
- The key is read from the environment only, never logged or returned; the browser never calls Pelican.
- Set `ALLOWED_ORIGIN` to the site's origin (trailing `/` is stripped): otherwise only the `X-Addon` header protects writes.
- Read-only rootfs, non-root, no capabilities; the only writable place is `/data`.
- Report vulnerabilities: `SECURITY.md`.

MIT licence, see `LICENSE`.
