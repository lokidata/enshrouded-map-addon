# Angular UI, two pages (step 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline). Use the official Angular skills (`angular-new-app` for Task 1, `angular-developer` for the others). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the static HTML/JS UI by an Angular app with the site's visual identity: a Serveur page and a Mods page with collapsible sections, no API change.

**Architecture:** `frontend/` (Angular 22, standalone, signals, Vitest) built to static files that FastAPI serves under `/addon/` as today. Two lazy routes (`/addon/` Serveur, `/addon/mods` Mods). The site's `design-system/` is copied in. Backend untouched except the static mount (SPA fallback).

**Tech Stack:** Angular 22 (same versions as the site: `@angular/*` ^22.2, TypeScript ~6.0, Vitest ^5, angular-eslint 22.6, Playwright + `@axe-core/playwright`), FastAPI `StaticFiles`, Docker multi-stage with Node.

**Spec:** `docs/superpowers/specs/2026-11-16-ui-redesign-and-server-config-design.md` (step 1). The settings editor (step 2) gets its own plan.

## Global Constraints
- Same API, same behaviour: every rule of `docs/RULES.md` (levels, confirmations strictly `confirm: true`, French messages, 429 wait, `X-Addon: 1` on writes, states unknown after a failed `/status`) is kept.
- CSP: `default-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` (only change: `base-uri`, Angular needs `<base href>`) (no inline script, no inline style: `optimization.styles.inlineCritical: false`, no `style=""` attributes, use classes; check in the browser console).
- Site's Angular rules (copy `frontend/CLAUDE.md` of the site into `frontend/CLAUDE.md`): no `standalone: true`, no explicit OnPush, signals, `input()/output()`, native control flow, `@Service`, `inject()`, no `ngClass/ngStyle`, no `any`. AXE and WCAG AA must pass.
- Design rules: tokens only (no hex outside `ds/tokens.css`), no `background-attachment: fixed`, no large blurred shadows, `prefers-reduced-motion` kept; a design guard script (`scripts/check-design.mjs`, adapted from the site's) runs in `npm run lint`.
- Supply chain: `package-lock.json` committed, `npm ci --ignore-scripts`, `npm audit --audit-level=high` in CI, Dependabot npm, Node image pinned by digest, final image still read-only, non-root, no Node.
- UI text in French. Only **chestsort** and **storage** are described on the Mods page.
- Python tests that checked the old JS/HTML strings (`tests/test_static.py`) are replaced by Vitest and Playwright tests; the other Python tests are untouched.

## Review Focus
- Deep link `/addon/mods` loaded directly (reload) must serve the app, while `/addon/api/...` unknown paths stay 404 JSON and `/addon/ds/...` assets never fall back to HTML.
- A `read`-level user or a server without `CHESTSORT_FILE`: Mods section 2 is hidden, section 1 readable, no error.
- 401 (not logged in), 503 (site down), 502 (panel down) on every card: a readable French message, never a blank page or an uncaught error.
- Section defaults (1 open, 2 closed) hold when `localStorage` throws.
- Status polling stops while the tab is hidden and does not stack requests; a failed read leaves the state `unknown` (power buttons disabled).
- The signed download URL is never rendered in the page, only navigated to.

---

### Task 1: Scaffold, design system, build and serving

**Files:**
- Create: `frontend/` (via the `angular-new-app` skill: Angular 22, standalone, routing, no SSR, strict, Vitest), `frontend/CLAUDE.md`, `frontend/src/ds/` (copy of the site's `design-system/` without `index.html`, plus `NOTICE.md`), `frontend/scripts/check-design.mjs`, `frontend/e2e/` (empty)
- Modify: `frontend/angular.json` (`outputPath` to `frontend/dist`, `baseHref: "/addon/"`, styles `src/ds/codex.css` then `src/styles.css`, `inlineCritical: false`), `src/addon/api.py` (static mount), `tests/test_api.py` or a new `tests/test_spa.py`
- Delete (at the end of Task 4, not here): `src/addon/static/`, `tests/test_static.py`

**Interfaces:**
- Produces: setting `ADDON_STATIC_DIR` (default `frontend/dist/browser` relative to the image's `/srv`; dev override) read by `create_app`; class `SpaFiles(StaticFiles)` whose `get_response(path, scope)` returns `index.html` when the path has no file extension and is not under `api/`, else the normal 404.

- [ ] **Step 1: Failing tests** (`tests/test_spa.py`): `test_deep_link_serves_the_app` (`GET /addon/mods` → 200, `text/html`, contains `<app-root`), `test_unknown_asset_is_404` (`GET /addon/ds/nope.woff2` → 404), `test_unknown_api_path_is_not_html` (`GET /addon/api/nope` with a session → 404 JSON), `test_csp_header_on_the_app` (header equals the CSP above). They use a temp dir with a fake `index.html` through `ADDON_STATIC_DIR`.
- [ ] **Step 2:** `uv run pytest tests/test_spa.py -q` → FAIL.
- [ ] **Step 3:** implement `SpaFiles` and the setting in `api.py`/`config.py`; scaffold `frontend/` with the skill, add the design system, `angular.json` settings, `npm run lint` including the design guard, and an empty `app.routes.ts` with two lazy routes `''` (Server) and `mods` (Mods) showing a placeholder.
- [ ] **Step 4:** `uv run pytest -q`; `cd frontend && npm ci --ignore-scripts && npm run lint && npm run build && npx ng test --watch=false`; run `uvicorn` with `ADDON_STATIC_DIR=frontend/dist/browser` and open `/addon/` and `/addon/mods` in the browser pane: fonts load, **no CSP error in the console**.

### Task 2: Core services (API, session, status)

**Files:** Create `frontend/src/app/core/api.ts`, `reasons.ts`, `session.ts`, `status.ts` and their `*.spec.ts`

**Interfaces:**
- `class ApiError { status: number; detail?: string; wait?: number; errors?: string[]; backup?: string }`
- `@Service Api { get<T>(path: string): Promise<T>; post<T>(path: string, body: unknown): Promise<T>; put<T>(path: string, body: unknown): Promise<T> }` (relative to `/addon/api`, `credentials: same-origin`, writes send `X-Addon: 1` and JSON; a non-2xx throws `ApiError`)
- `failure(err: unknown): string` in `reasons.ts` (French text for 429 with wait, the reasons table of the old `app.js`, 401, 503, 502, fallback `Erreur inattendue (code).`, plus `backup_not_ready`)
- `@Service Session { me: Signal<Me | null>; error: Signal<string>; load(): Promise<void> }` where `Me = { username: string; is_admin: boolean; level: 'read' | 'action' | null; backup_filtered: boolean; chestsort: boolean }`; `canAct = computed(() => me()?.level === 'action')`
- `@Service Status { state: Signal<'unknown' | string>; info: Signal<ServerStatus | null>; error: Signal<string>; refresh(): Promise<void>; start(): void }` (poll every 15 s only while `document.hidden` is false, no overlapping call, a failed read sets state `unknown`)

- [ ] **Step 1: Failing tests** (Vitest, `fetch` stubbed): `api.spec.ts` (writes carry `X-Addon: 1`; a 429 carries `retry_after` as `wait`; a 409 body `detail` is kept); `reasons.spec.ts` (each reason of the old table, 429 with and without wait, unknown code); `status.spec.ts` (a failed read gives `unknown`; two `refresh()` at once make one request; no request while hidden).
- [ ] **Step 2:** run → FAIL. **Step 3:** implement. **Step 4:** run → PASS, lint clean.

### Task 3: Layout and Serveur page

**Files:** Create `frontend/src/app/layout/` (shell with header, `nav.top`, state pill, message area), `frontend/src/app/ui/section.ts` (collapsible section), `frontend/src/app/server/` (page, `power.ts`, `backups.ts`, `journal.ts`, `access.ts`, `confirm-dialog.ts`) with specs

**Interfaces:**
- Consumes: Task 2 services.
- `Section` component: `<app-section title="..." [open]="true" storageKey="server-pelican">` wraps `<details>`/`<summary>`; remembers its state in `localStorage` inside try/catch; default `open` input applies when storage fails.
- `ConfirmDialog`: `<app-confirm-dialog>` with `open(opts: { title: string; label: string; ok: string }): Promise<boolean>` using a native `<dialog>`; the OK button stays disabled until its checkbox is ticked.
- Server page sections: **Pelican** (open: state card with CPU, memory, disk, uptime; Start/Stop/Restart for `action` only, Start only when `offline`, Stop and Restart only when `running`, all disabled when state unknown or while a request runs; backups table with create and download buttons), **Journal** (closed), **Accès** (closed, admin only).

- [ ] **Step 1: Failing tests:** `section.spec.ts` (default open/closed; state restored; works when `localStorage` throws); `power.spec.ts` (button enabled matrix from the state; Stop sends `{signal: 'stop', confirm: true}` only after the dialog confirmation; Start sends no confirm; 429 shows the wait; after an action status, backups and journal reload); `backups.spec.ts` (status labels `en cours` and `échec`; the create button asks the full-backup dialog when `backup_filtered` is false and sends `confirm_full: true`; download button only for finished successful backups and only for `action`; it navigates to the returned URL and never renders it; list error cleared by the next success); `access.spec.ts` (admin only; PUT level change; user list error message).
- [ ] **Step 2:** run → FAIL. **Step 3:** implement (signals, native control flow, no inline style). **Step 4:** PASS; lint; build.

### Task 4: Mods page, chestsort port, removal of the old UI

**Files:** Create `frontend/src/app/mods/` (page, `mods-text.ts` content, `chestsort/chestsort.logic.ts`, `chestsort/chestsort.ts`) with specs; Delete `src/addon/static/`, `tests/test_static.py`

**Interfaces:**
- `chestsort.logic.ts`: pure functions ported one-to-one from `src/addon/static/chestsort.js` (add, rename, delete category; lines to words/items keeping non-empty lines exactly, counters, filter, stale-preview version check). Same API calls: `GET /chestsort`, `POST /chestsort/preview`, `PUT /chestsort`, `GET /chestsort/backups`, `POST /chestsort/restore`.
- Mods page: **Les mods** (open: two sub-groups, `chestsort` and `storage`, French text from ShroudLink's README: chest renamed to categories, deposit or Quick Stack Station fills it, equipped and hand items never deposited, file reloaded live; storage = MODS → Storage grid of all chests within 40 m, biggest stacks first, search, click to take from every chest, needs the players' client addon), **Catégories de coffres** (closed; hidden when `me.chestsort` is false; read-only for level `read`).

- [ ] **Step 1: Failing tests:** `chestsort.logic.spec.ts` (every case the old behaviour had: spaces kept, only fully empty lines dropped, counters, filter keeps unfiltered lines when saving, preview answer after a further edit is dropped); `chestsort.spec.ts` (Save disabled until a preview without error; save asks the "J'ai relu les changements" dialog and sends `confirm: true`; `changed_elsewhere` asks to reload; `rollback_failed` names the copy; read level sees no edit buttons; section hidden when `me.chestsort` is false); `mods.spec.ts` (section 1 open, 2 closed; text mentions chestsort and storage and none of `assistants`, `meter`, `gemforge`).
- [ ] **Step 2:** run → FAIL. **Step 3:** implement; port the logic by reading `chestsort.js` side by side. **Step 4:** PASS; then delete the old static files and `tests/test_static.py`; `uv run pytest -q` still green.

### Task 5: Build in Docker and CI, Playwright and AXE, docs

**Files:** Modify `Dockerfile`, `.github/workflows/ci.yml` (job `frontend`), `.github/dependabot.yml` (npm in `/frontend`), `Makefile`, `docs/RULES.md` (UI section), `README.md`; Create `frontend/e2e/pages.spec.ts`, `frontend/playwright.config.ts`

**Interfaces:**
- Dockerfile: stage `web` on a `node:<lts>-slim@sha256:...` image (`npm ci --ignore-scripts`, `npm run build`), then `COPY --from=web /web/frontend/dist/browser /srv/frontend/dist/browser` in the final Python image; `ADDON_STATIC_DIR` default points there; image stays non-root, no Node.
- `e2e/pages.spec.ts`: Playwright with `page.route('**/addon/api/**')` mocking the API (no real server): both pages load, sections default open/closed, AXE (WCAG A and AA) clean on each page and with a section opened, no console error (covers CSP), phone width without horizontal scroll, light and dark scheme.

- [ ] **Step 1:** write the e2e test (fails until the build is served). **Step 2:** Dockerfile and CI changes; `docker build` locally and `docker run` the image, open `/addon/` and `/addon/mods` through it (a fake site/Pelican is not needed for the shell and error states). **Step 3:** docs. **Step 4:** `make check` equivalent: ruff, mypy, bandit, pip-audit, pytest, `npm audit`, lint, build, Vitest, Playwright, Trivy-equivalent step in CI. **Do not commit or open the PR before the owner has tested.**

## Self-review
- Spec step 1 covered: design system (T1), Serveur page with Pelican, journal, access (T3), Mods page and chestsort (T4), docs and checks (T5). The settings editor and its section are step 2.
- Names used consistently: `Api`, `Session`, `Status`, `failure`, `Section`, `ConfirmDialog`, `SpaFiles`, `ADDON_STATIC_DIR`.
- Risks to say at the end: the rewrite of verified code (chestsort, confirmations) is re-tested only by unit and mocked e2e tests, not on the real panel; the repo gains many npm dependencies.
