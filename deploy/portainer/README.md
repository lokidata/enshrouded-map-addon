# Deploying the add-on with Portainer

The **Publish image** workflow pushes `ghcr.io/lokidata/enshrouded-map-addon` (`latest`, `sha-xxxxxxx`, `1.2.3`, `1.2`) on every push to `main` and on `v*.*.*` tags. Pin `IMAGE_TAG` for a stable server.

The add-on is one more service of the **site's own stack** (same networks, one deployment, no ordering problem). Nothing changes for the site while `ADDON_URL` is empty.

## 1. Panel side (once)

- A dedicated panel user with **no role**, sub-user of the game server only, with: `control.start`, `control.stop`, `control.restart`, `file.read`, `file.read-content`, `file.create`, `file.update`, `backup.create`, `backup.read`.
- A client API key for that user, restricted to the address the panel sees for the Docker host. Paste it into Portainer only.

## 2. Edit the site stack

- `api` and `web`, `environment`: add `ADDON_URL: ${ADDON_URL:-}`.
- `web`: optionally add `addon: {condition: service_healthy}` under `depends_on` (starts the add-on first). Not required: the site resolves the add-on's name at request time (needs the site image from enshrouded-map#80 or later), so a missing add-on only makes `/addon/` answer 502.
- Add the `addon` service from `service.example.yml`; create its data folder: `mkdir -p /opt/enshrouded/addon && chown 10001:10001 /opt/enshrouded/addon`.
- Stack variables: `ADDON_URL=http://addon:8000`, `PELICAN_URL`, `PELICAN_SERVER_ID`, `PELICAN_API_KEY`, `ALLOWED_ORIGIN` (the origin players open).

## 3. Check

As the administrator: the menu shows "Serveur de jeu" and `/addon/` shows the status. `pelican_denied`: key IP restriction, user permissions or panel name resolution (hairpin NAT: add a local DNS record or `extra_hosts`). `pelican_unavailable`: panel unreachable or unexpected answer.

## Turning it off

Empty `ADDON_URL` and remove the `addon` service (and its `depends_on`).
