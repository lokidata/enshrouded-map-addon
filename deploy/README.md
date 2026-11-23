# Deployment notes

- `compose.example.yml`: the service, read-only, non-root, `/tmp` in tmpfs, one volume `/data` (SQLite file). Join it to the network the site's web container uses (`SITE_URL` must reach the site API).
- `nginx.example.conf`: what the site generates for each add-on container (`ADDONS` or the `ADDON_URL` alias). You do not install it by hand; it is documented here to show the public path (`/addon/<key>/`, for example `/addon/main/`, stripped before it reaches the add-on) and headers.
- Portainer: build or pull the image, create a stack from `compose.example.yml`, and set `PELICAN_API_KEY` as a stack variable (paste the `pacc_...` key there; it is shown once by Pelican). Set `ADDON_URL` (origin only, for example `http://addon:8000`; or `ADDONS=main=http://addon:8000`) on the site's web AND api containers (the web container proxies, the API reads the manifests) and redeploy them. These are site-side settings: the add-on never knows its key. Then, in the site's Administration, enable each entry and grant access.
- Image: `make lock` regenerates `requirements.lock` (hash-locked) after any dependency change.
- Back up the `addon-data` volume only if you want to keep the journal (1 day); it holds no access list (the site keeps them) and its `access_v2` table is dormant.
- The chestsort editor shows item names and pictures from the site's `item-names.json` (served by the site with its other data files; optional: without it the editor still works with internal names).
- Revoke: delete the key in Pelican (Account > API keys) or remove the sub-user from the server; the add-on stops working at once.
