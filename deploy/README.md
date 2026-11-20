# Deployment notes

- `compose.example.yml`: the service, read-only, non-root, `/tmp` in tmpfs, one volume `/data` (SQLite file). Join it to the network the site's web container uses (`SITE_URL` must reach the site API).
- `nginx.example.conf`: what the site generates when its `ADDON_URL` is set. You do not install it by hand; it is documented here to show the path (`/addon/`) and headers.
- Portainer: build or pull the image, create a stack from `compose.example.yml`, and set `PELICAN_API_KEY` as a stack variable (paste the `pacc_...` key there; it is shown once by Pelican). Set `ADDON_URL` (origin only, for example `http://addon:8000`) on the site's web container and redeploy it.
- Image: `make lock` regenerates `requirements.lock` (hash-locked) after any dependency change.
- Back up the `addon-data` volume only if you want to keep the access list; the journal lives 1 day.
- The chestsort editor shows item names and pictures from the site's `item-names.json` (served by the site with its other data files; optional: without it the editor still works with internal names).
- Revoke: delete the key in Pelican (Account > API keys) or remove the sub-user from the server; the add-on stops working at once.
