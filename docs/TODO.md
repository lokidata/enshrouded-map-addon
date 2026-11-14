# TODO

Open work of the add-on (deliveries 1 to 3 are done: status, access list, power, backups, chestsort editor).

## Delivery 3: chestsort categories editor
- [x] View and edit `chestsort_categories.json` with validation, diff, dated `.bak` copies and restore; off unless `CHESTSORT_FILE` is set. To do by the maintainer: try it on a copy of the file first, never in place.

## Later
- [ ] **Download a backup from the page**: the dedicated panel account already has `backup.download`. The panel's client API gives a one-time signed URL (`GET /servers/{server}/backups/{backup}/download`, answer `{object: "signed_url", attributes: {url}}`, 400 with `message` when it cannot be downloaded). Plan: `GET /addon/api/backups/{uuid}/download` for level `action` (a backup is the whole save), journalled, rate-limited; the add-on returns the URL and the page opens it (the browser must reach the node's address: check it on the real stack before building the UI); validate `uuid` as a UUID; never log the signed URL (it is a credential); only completed and successful backups (`completed_at` set, `is_successful` true). Delete, restore and lock stay out of the add-on.
- [ ] **Backup list pagination**: the panel paginates `GET /backups` (`meta.pagination`); only page 1 is read, so a server with many backups may not show the newest ones.
- [ ] **Show the tail of `shroudlink.log` after a chestsort save** (mod errors are only reported there; path unverified; needs `file.read-content`, already granted).
- [ ] **Chestsort `.bak-` cleanup**: copies accumulate (no `file.delete` permission); today cleaned by hand in the panel.
