# Style contract with the site

The add-on screens are mounted by the site in `<div data-addon>`. The site's `frontend/src/app/workshop/workshop.css` styles that wrapper like its own screens (scope selector `[data-addon]`, the only one added for add-ons). The add-on brings no design system: it uses the site's tokens (`--gold`, `--bad`, `--panel`, ...) and the classes below. A new token or class belongs to the site.

| Need | Use | Where it comes from |
| --- | --- | --- |
| Buttons | plain `<button>`; `.danger` (red text) | site (`button`, `button.danger`) |
| Main action | `<button class="primary">` | add-on (`button.primary`, ember edge) |
| Fields | plain `<select>`; `<textarea>` | site / add-on (textarea) |
| Sections | `<details class="sec"><summary>` | add-on (`details.sec`) |
| Tables | `<table class="entries-table">` | site |
| Key / value figures | `.tiles` > `.tile` > `.k` + `.v` (`.v.up` green) | site (added with the add-ons) |
| Row of buttons | `.actions` | site |
| Notes | `.meta`, `.hint`, `.empty` | site |
| Hidden text for screen readers | `.sr` | site |
| Error line | `.err` | add-on |
| Confirmation dialog | `<dialog>` | add-on (scoped `dialog`) |

Rules, checked by `npm run lint` (`scripts/check-scope.mjs`, `scripts/check-design.mjs`): every top-level rule of `src/styles.css` starts with `[data-addon]`, no hex colour, no inline style, no `text-transform: uppercase`.
