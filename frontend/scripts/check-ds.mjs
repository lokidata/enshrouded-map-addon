// Drift check: src/ds/ is a copy of the site's design-system/ (lokidata/enshrouded-map), pinned to a commit in
// src/ds/SOURCE. This fails when a file here differs from the site's at that commit, or when one is missing or extra.
//   node scripts/check-ds.mjs                 compare (run by `npm run lint`)
//   node scripts/check-ds.mjs --update [ref]  copy the site's files at ref (default: the head of main) and pin it
// Offline, the check is skipped with a warning (in CI, where CI is set, a network failure fails it).
import { mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';

const DS = new URL('../src/ds/', import.meta.url).pathname;
const SOURCE_FILE = join(DS, 'SOURCE');
// Kept only in the site's folder: not part of the copy.
const NOT_COPIED = new Set(['index.html', 'README.md']);
// Ours, not the site's.
const OURS = new Set(['NOTICE.md', 'SOURCE']);

const source = Object.fromEntries(
  readFileSync(SOURCE_FILE, 'utf8')
    .split('\n')
    .filter((l) => l.includes('='))
    .map((l) => l.split('=').map((s) => s.trim())),
);
const headers = {
  'user-agent': 'enshrouded-map-addon-check-ds',
  ...(process.env.GITHUB_TOKEN ? { authorization: `Bearer ${process.env.GITHUB_TOKEN}` } : {}),
};

/** A problem of the network or of GitHub's limits, not of our files: the check is skipped, not failed. */
class Unreachable extends Error {}

async function get(url, binary = false) {
  let res;
  try {
    res = await fetch(url, { headers });
  } catch (err) {
    throw new Unreachable(`${url}: ${err.cause?.code ?? err.message}`);
  }
  if (res.status === 403 || res.status === 429 || res.status >= 500)
    throw new Unreachable(`${url}: HTTP ${res.status}`);
  if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`); // a wrong repo or ref in SOURCE: fail
  return binary ? Buffer.from(await res.arrayBuffer()) : res.json();
}

/** The files of the site's design-system/ at a commit, relative to that folder. */
async function remoteFiles(ref) {
  const tree = await get(
    `https://api.github.com/repos/${source.repo}/git/trees/${ref}?recursive=1`,
  );
  if (tree.truncated) throw new Error('the site tree is too big for one listing');
  const prefix = `${source.path}/`;
  return tree.tree
    .filter((e) => e.type === 'blob' && e.path.startsWith(prefix))
    .map((e) => e.path.slice(prefix.length))
    .filter((f) => !NOT_COPIED.has(f));
}

const rawUrl = (ref, file) =>
  `https://raw.githubusercontent.com/${source.repo}/${ref}/${source.path}/${file}`;

function* localFiles(dir = DS) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) yield* localFiles(path);
    else if (!OURS.has(relative(DS, path))) yield relative(DS, path);
  }
}

async function update(ref) {
  if (!ref) ref = (await get(`https://api.github.com/repos/${source.repo}/commits/main`)).sha;
  const files = await remoteFiles(ref);
  for (const file of localFiles()) if (!files.includes(file)) rmSync(join(DS, file));
  for (const file of files) {
    mkdirSync(dirname(join(DS, file)), { recursive: true });
    writeFileSync(join(DS, file), await get(rawUrl(ref, file), true));
  }
  writeFileSync(SOURCE_FILE, `repo=${source.repo}\npath=${source.path}\nref=${ref}\n`);
  console.log(`src/ds copied from ${source.repo}@${ref.slice(0, 7)} (${files.length} files).`);
}

async function check() {
  const files = await remoteFiles(source.ref);
  const local = [...localFiles()];
  const problems = [
    ...files.filter((f) => !local.includes(f)).map((f) => `${f}: missing here`),
    ...local.filter((f) => !files.includes(f)).map((f) => `${f}: not in the site's design-system/`),
  ];
  for (const file of files.filter((f) => local.includes(f))) {
    const theirs = await get(rawUrl(source.ref, file), true);
    if (Buffer.compare(theirs, readFileSync(join(DS, file))) !== 0)
      problems.push(`${file}: differs`);
  }
  if (problems.length) {
    console.error(
      `Design system drift: src/ds differs from ${source.repo}@${source.ref.slice(0, 7)}.\n` +
        problems.join('\n') +
        "\n\nTo take the site's latest: node scripts/check-ds.mjs --update (then commit src/ds).",
    );
    process.exit(1);
  }
  console.log(`Design system: src/ds matches ${source.repo}@${source.ref.slice(0, 7)}.`);
}

const args = process.argv.slice(2);
try {
  if (args[0] === '--update') await update(args[1]);
  else await check();
} catch (err) {
  if (!(err instanceof Unreachable)) throw err;
  const msg = `Design system check skipped (${err.message}).`;
  if (process.env.CI) {
    console.error(msg);
    process.exit(1);
  }
  console.warn(msg);
}
