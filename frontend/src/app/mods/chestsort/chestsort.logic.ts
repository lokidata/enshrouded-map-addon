import { ApiError } from '../../core/api';
import { Translate } from '../../core/i18n';
import { Key } from '../../core/lang.fr';
import { failure } from '../../core/reasons';

export interface Category {
  words: string[];
  items: string[];
}
export type Cats = Record<string, Category>;
export interface Preview {
  errors: string[];
  warnings: string[];
  changed: boolean;
  diff: string[];
}

const CODES = new Set([
  'changed_elsewhere',
  'too_large',
  'file_invalid',
  'invalid_content',
  'backup_failed',
  'verify_failed',
  'rollback_failed',
  'file_not_utf8',
  'invalid_backup_name',
  'unknown_backup',
  'confirmation_required',
]);

/** Only empty lines are dropped: a line is kept exactly as typed (the diff shows it). */
export const lines = (text: string): string[] => text.split('\n').filter((l) => l !== '');

const sameName = (a: string, b: string): boolean => a.toLowerCase() === b.toLowerCase();

/** The sentence for a failed chestsort call: reasons first, the copy to restore, then the messages. */
export function csFailure(err: unknown, t: Translate): string {
  if (!(err instanceof ApiError)) return failure(err, t);
  let text =
    err.detail && CODES.has(err.detail) ? t(`cs.err.${err.detail}` as Key) : failure(err, t);
  if (err.backup) text += t('cs.restore_copy', { backup: err.backup });
  return err.errors?.length ? `${text}\n- ${err.errors.join('\n- ')}` : text;
}

/** A new empty category, or the reason it cannot be added. */
export function addCategory(cats: Cats, raw: string): { cats: Cats } | { error: Key } {
  const name = raw.trim();
  if (!name) return { error: 'cs.name_required' };
  if (Object.keys(cats).some((n) => sameName(n, name))) return { error: 'cs.name_taken' };
  return { cats: { ...cats, [name]: { words: [], items: [] } } };
}

/** Renaming keeps the order of the categories. */
export function renameCategory(
  cats: Cats,
  from: string,
  raw: string,
): { cats: Cats } | { error: Key } | null {
  const name = raw.trim();
  if (!name || name === from) return null;
  if (Object.keys(cats).some((n) => n !== from && sameName(n, name)))
    return { error: 'cs.name_taken' };
  const next: Cats = {};
  for (const [n, c] of Object.entries(cats)) next[n === from ? name : n] = c;
  return { cats: next };
}

export function deleteCategory(cats: Cats, name: string): Cats {
  const next = { ...cats };
  delete next[name];
  return next;
}

/** The items whose displayed name (`shown`, by default the item itself) contains the query. */
export function filterItems(
  items: string[],
  query: string,
  shown: (item: string) => string = (i) => i,
): string[] {
  const q = query.trim().toLowerCase();
  return q ? items.filter((i) => shown(i).toLowerCase().includes(q)) : items;
}

/** The text of the diff box: errors, warnings, then the changes. */
export function previewText(r: Preview, t: Translate): string {
  const out: string[] = [];
  if (r.errors.length) out.push(t('cs.p.errors'), ...r.errors.map((e) => `- ${e}`), '');
  if (r.warnings.length) out.push(t('cs.p.warnings'), ...r.warnings.map((w) => `- ${w}`), '');
  out.push(r.changed ? t('cs.p.changes') : t('cs.p.none'), ...r.diff);
  return out.join('\n');
}

// ---- items: one item belongs to one category only (the server refuses a file where it is in two) ----

/** An item the catalogue has no name for (the game gives it none): its internal name made readable. */
export const prettyName = (item: string): string =>
  item.replace(/^_+/, '').replace(/_+/g, ' ').trim();

export const MAX_ITEM = 200;
const same = (a: string, b: string): boolean => a.toLowerCase() === b.toLowerCase();

/** What is typed or pasted: one name per line, or separated by commas or semicolons; each name once. */
export function parseNames(text: string): string[] {
  const out: string[] = [];
  for (const raw of text.split(/[\n,;]+/)) {
    const n = raw.trim();
    if (n && !out.some((o) => same(o, n))) out.push(n);
  }
  return out;
}

export function itemProblem(name: string): Key | null {
  // eslint-disable-next-line no-control-regex
  return name.length > MAX_ITEM || /[\u0000-\u001f\u007f]/.test(name) ? 'cs.item_invalid' : null;
}

/** The category holding the item (any case), leaving `except` out. */
export function ownerOf(cats: Cats, item: string, except?: string): string | null {
  for (const [n, c] of Object.entries(cats))
    if (n !== except && c.items.some((i) => same(i, item))) return n;
  return null;
}

export interface Conflict {
  item: string;
  from: string;
}
export interface Added {
  cats: Cats;
  added: string[];
  present: string[]; // already in this category
  conflicts: Conflict[]; // in another category: nothing moves until the user says so
  invalid: string[];
}

export function addItems(cats: Cats, cat: string, names: string[]): Added {
  const r: Added = { cats, added: [], present: [], conflicts: [], invalid: [] };
  const items = [...(cats[cat]?.items ?? [])];
  for (const name of names) {
    const from = ownerOf(cats, name, cat);
    if (itemProblem(name)) r.invalid.push(name);
    else if (items.some((i) => same(i, name))) r.present.push(name);
    else if (from) r.conflicts.push({ item: name, from });
    else {
      items.push(name);
      r.added.push(name);
    }
  }
  r.cats = { ...cats, [cat]: { ...cats[cat], items } };
  return r;
}

/** The user chose to move: each item leaves its category and joins `cat`. */
export function moveItems(cats: Cats, cat: string, conflicts: Conflict[]): Cats {
  const next: Cats = { ...cats };
  const items = [...cats[cat].items];
  for (const { item, from } of conflicts) {
    next[from] = { ...next[from], items: next[from].items.filter((i) => !same(i, item)) };
    if (!items.some((i) => same(i, item))) items.push(item);
  }
  next[cat] = { ...next[cat], items };
  return next;
}

export function removeItem(cats: Cats, cat: string, item: string): Cats {
  return { ...cats, [cat]: { ...cats[cat], items: cats[cat].items.filter((i) => i !== item) } };
}

/** Items a loaded file already holds in two categories: the server will refuse a save until fixed. */
export function duplicates(cats: Cats): { item: string; cats: string[] }[] {
  const seen = new Map<string, { item: string; cats: string[] }>();
  for (const [n, c] of Object.entries(cats))
    for (const i of c.items) {
      const e = seen.get(i.toLowerCase()) ?? { item: i, cats: [] };
      if (!e.cats.includes(n)) e.cats.push(n);
      seen.set(i.toLowerCase(), e);
    }
  return [...seen.values()].filter((e) => e.cats.length > 1);
}
