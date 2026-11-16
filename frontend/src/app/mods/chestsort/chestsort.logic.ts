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

export function filterItems(items: string[], query: string): string[] {
  const q = query.trim().toLowerCase();
  return q ? items.filter((i) => i.toLowerCase().includes(q)) : items;
}

/** The text of the diff box: errors, warnings, then the changes. */
export function previewText(r: Preview, t: Translate): string {
  const out: string[] = [];
  if (r.errors.length) out.push(t('cs.p.errors'), ...r.errors.map((e) => `- ${e}`), '');
  if (r.warnings.length) out.push(t('cs.p.warnings'), ...r.warnings.map((w) => `- ${w}`), '');
  out.push(r.changed ? t('cs.p.changes') : t('cs.p.none'), ...r.diff);
  return out.join('\n');
}
