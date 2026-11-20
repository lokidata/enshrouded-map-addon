// Scope guard: the add-on's CSS must not reach the site it is mounted in (see docs/style-contract.md).
// Every top-level rule of src/styles.css starts with [data-addon]; no hex colour; no inline style in a template.
// Run by `npm run lint`.
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const HEX = /#[0-9a-fA-F]{3,8}\b/;

/** Problems of one stylesheet, as strings. Only the selectors at depth 0 are checked: nested ones inherit them. */
export function checkCss(source) {
  const css = source.replace(/\/\*[\s\S]*?\*\//g, '');
  const problems = [];
  let depth = 0;
  let prelude = '';
  for (const ch of css) {
    if (ch === '{') {
      if (depth === 0) {
        const sel = prelude.trim();
        const list = sel.split(',').map((s) => s.trim());
        if (sel.startsWith('@') || !list.every((s) => s.startsWith('[data-addon]')))
          problems.push(`rule outside [data-addon]: ${sel.slice(0, 60)}`);
      }
      depth++;
      prelude = '';
    } else if (ch === '}') {
      depth--;
      prelude = '';
    } else if (ch === ';' && depth === 0) {
      problems.push(`top-level statement: ${prelude.trim().slice(0, 60)}`);
      prelude = '';
    } else prelude += ch;
  }
  const hex = css.match(HEX);
  if (hex) problems.push(`hex colour ${hex[0]}: use a site token (var(--gold)...)`);
  return problems;
}

export function checkTemplate(source) {
  return /\sstyle=|\[style[.\]]|\[attr\.style\]/.test(source) ? ['inline style in a template'] : [];
}

function* files(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) yield* files(p);
    else yield p;
  }
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const src = fileURLToPath(new URL('../src', import.meta.url));
  const found = checkCss(readFileSync(join(src, 'styles.css'), 'utf8')).map(
    (p) => `styles.css: ${p}`,
  );
  for (const f of files(join(src, 'app')).filter(
    (f) => f.endsWith('.ts') && !f.endsWith('.spec.ts'),
  ))
    found.push(
      ...checkTemplate(readFileSync(f, 'utf8')).map((p) => `${f.slice(src.length + 1)}: ${p}`),
    );
  if (found.length) {
    console.error(found.join('\n'));
    process.exit(1);
  }
  console.log('Scope guard: the add-on styles stay under [data-addon], no hex, no inline style.');
}
