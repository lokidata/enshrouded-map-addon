# TODO

Open work of the add-on (deliveries 1 to 3 are done: status, access list, power, backups, chestsort editor).

## Delivery 3: chestsort categories editor
- [x] View and edit `chestsort_categories.json` with validation, diff, dated `.bak` copies and restore; off unless `CHESTSORT_FILE` is set. To do by the maintainer: try it on a copy of the file first, never in place.

## Later
- [ ] **Console of the game server** (read-only, relayed by the add-on, level `action`): design in `docs/superpowers/specs/2026-11-16-ui-redesign-and-server-config-design.md` (step 3). Needs the `websocket.connect` permission.
- [ ] **Backup list pagination**: the panel paginates `GET /backups` (`meta.pagination`); only page 1 is read, so a server with many backups may not show the newest ones.
- [ ] **Show the tail of `shroudlink.log` after a chestsort save** (mod errors are only reported there; path unverified; needs `file.read-content`, already granted).
- [ ] **Chestsort `.bak-` cleanup**: copies accumulate (no `file.delete` permission); today cleaned by hand in the panel.
