# TODO

Open work of the add-on (deliveries 1 to 4 are done: status, access managed by the site, power, backups, chestsort editor, integration into the site as custom elements).

## Delivery 3: chestsort categories editor
- [x] View and edit `chestsort_categories.json` with validation, diff, dated `.bak` copies and restore; off unless `CHESTSORT_FILE` is set. To do by the maintainer: try it on a copy of the file first, never in place.

## Delivery 4: integration into the site
- [x] Two custom elements mounted by the site, manifest, access managed by the site (Administration dialog), site design system, FR/EN/DE; chestsort editor with item catalogue, picker popup, "one item, one category" and file download.

## SDK phase 1
- [x] Manifest v2 (static, per-entry `script`/`styles`), identity and level from the site's `/api/v1/addons/<entry>/me`, access lists removed from the add-on. Awaiting local testing with the site branch `feat/addon-sdk-phase1`.

## Later
- [ ] **Chestsort wildcards and removals**: the mod accepts `Food_T1_*` and a leading `-`; the editor treats them as plain names (no picture, no duplicate detection).
- [ ] **German item names**: export the game's German texts (`De_De.tsv`) on the PC that runs the pipeline and rerun it; until then `item-names.json` has English for the items without a German text.
- [ ] **Try the chestsort file without "Nourriture"** on the real server (a cleaned copy has no item in two categories): check how the mod reacts to a missing category and to the words that went with it.
- [ ] **Console of the game server** (read-only, relayed by the add-on, level `action`): design in `docs/superpowers/specs/2026-11-16-ui-redesign-and-server-config-design.md` (step 3). Needs the `websocket.connect` permission.
- [ ] **Backup list pagination**: the panel paginates `GET /backups` (`meta.pagination`); only page 1 is read, so a server with many backups may not show the newest ones.
- [ ] **Show the tail of `shroudlink.log` after a chestsort save** (mod errors are only reported there; path unverified; needs `file.read-content`, already granted).
- [ ] **Chestsort `.bak-` cleanup**: copies accumulate (no `file.delete` permission); today cleaned by hand in the panel.
