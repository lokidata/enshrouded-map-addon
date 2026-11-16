# UI redesign (two pages) and game-settings editor: design

## Why
The add-on works but looks bare. The owner wants the site's visual identity ("Codex of the Shroud") and two pages, and wants to change the **Custom game settings** of the server easily without hand-editing JSON.

## Goals
- Reuse the site's `design-system/` (tokens, fonts, `.plate`, `.btn`, ...); no new visual language.
- Page **Serveur** (`/addon/`): collapsible sections, 1 open by default, 2 closed.
  1. Pelican: status, start/stop/restart, backups (create, list, download). Journal and access list (admin) follow as closed sections 3 and 4; the status header stays visible on both pages.
  2. Game settings editor (new, step 2).
- Page **Mods** (`/addon/mods.html`): 1 open, 2 closed.
  1. What each installed mod is and does (grouped to read easily).
  2. The existing chestsort categories editor, unchanged (its ergonomics come later).
- Top navigation between the two pages; only sections the user may use are shown (levels and `CHESTSORT_FILE` rules unchanged).

## Non-goals / anti-goals
- No change to the site; the add-on stays strictly additive and optional.
- No framework or build step (static HTML + vanilla JS, strict CSP, `textContent` only).
- Never send passwords, ports or other keys of the server file to the browser; never rewrite them.
- No chestsort UX rework in this work.

## Approaches (chosen: B)
- A. "Send to server" button on the site's Game page: reuses its UI but changes the site. Rejected: breaks "additive".
- **B. Form inside the add-on, built from a table of settings copied from the site (`frontend/src/app/core/game-settings.model.ts`).** Chosen. Cost: the table lives in two places; updated by copy.
- C. Raw JSON editor: simplest, not "easy". Rejected.

## Design
**Step 1 (UI, no new backend).** Copy `design-system/` into `src/addon/static/ds/` with its licences (fonts OFL). Split the page into `index.html` (Serveur) and `mods.html`, sharing `app.css` (thin layer over the tokens) and a small `nav`. Sections are `<details class="plate">` with the site's heading style; default open state as above; the open state of each section may be remembered in `localStorage` (wrapped in try/catch). The existing JS is reused; `app.js` keeps the common helpers, `chestsort.js` loads only on the Mods page. Contrast and focus follow the design system rules.

**Step 2 (settings editor).** Env `SERVER_CONFIG_FILE` (Pelican path of the server JSON; editor shown only when set, like `CHESTSORT_FILE`).
- Routes under `/addon/api/server-config`: `GET` returns only `name`, `slotCount`, `gameSettingsPreset`, `gameSettings` (missing keys filled with defaults, flagged as default); `PUT` (level `action`, `X-Addon` guard, `confirm: true`) takes the same four keys.
- Validation server-side from a table (`settings.json`: key, kind number|enum|bool|duration, min, max, step, options, French label and help), identical to the site's ranges; unknown keys, out-of-range values and wrong types are 422 with the field names.
- Write path reuses the chestsort pipeline: read current → merge only the four keys → hash check (`changed_elsewhere`) → dated `.bak` copy and verify → write → read back and compare → rollback on any failure; canonical dump keeps the file's own formatting where possible; 1 MB limit; strict UTF-8; depth guard; global throttle (10 s); journalled without contents.
- Page: fields grouped as on the site's Game page; preset selector (values apply only with `Custom`, shown dimmed otherwise); durations in minutes (stored in nanoseconds); a "Revenir aux valeurs par défaut" per field; diff preview before saving; save asks the "J'ai relu les changements" dialog; after a save, a second dialog offers "Redémarrer maintenant" (existing power route, "J'ai prévenu les joueurs") or "Plus tard", saying the server reads the file only at start.
- Restore from a listed `.bak` as in chestsort.

**Mods page text.** Written in French from the ShroudLink README, limited to the mods really installed on the server (list to confirm by the owner before writing; unknown ones are not described).

## Left to the builder
Exact CSS of the nav and details sections, table format file name, wording of French labels (taken from the site's translations where they exist).

## My calls (to check)
- Journal and access list become closed sections 3 and 4 of the Serveur page.
- The "Mods" page lists mods as a short grouped text, not interactive.
- Settings table copied from the site, not fetched from it at runtime.
- Step 1 and step 2 are two separate PRs.

## Unverified
The real server file layout and path (read it once on the real panel when step 2 starts, only with the owner's go); how the mod set appears to the owner (list needed).
