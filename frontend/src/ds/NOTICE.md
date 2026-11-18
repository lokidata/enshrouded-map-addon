Copied from the site's `design-system/` (Codex of the Shroud, https://github.com/lokidata/enshrouded-map). Fonts are OFL (see `licenses/`).

The copy is pinned to a commit of the site in `SOURCE`. `npm run lint` runs `scripts/check-ds.mjs`, which fails when a file here differs from the site's at that commit (or is missing or extra). Do not edit these files here: change them in the site, then take them with:

    node scripts/check-ds.mjs --update

which copies the site's latest `main` and rewrites `SOURCE`; commit the result.
