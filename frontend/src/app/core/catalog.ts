import { Injectable, signal } from '@angular/core';
import type { Lang } from './i18n';

/**
 * [internal name, FR, EN, DE, picture guid or ""] — the site's `item-names.json`
 * (the game's `debugName`, what the chestsort file holds; the picture is `/items/<guid>.png`).
 */
export type CatalogRow = [string, string, string, string, string];

/** The item's name in the user's language. */
export const nameOf = (row: CatalogRow, lang: Lang): string =>
  row[lang === 'fr' ? 1 : lang === 'de' ? 3 : 2];

/** The picture of an item, or null when the game has none. */
export const iconOf = (row: CatalogRow): string | null =>
  /^[0-9a-f-]{36}$/.test(row[4]) ? `/items/${row[4]}.png` : null;

/**
 * The site publishes the item names next to its other data files (same origin, behind the same session).
 * Optional: without the file the editor still works, by typing internal names.
 */
@Injectable({ providedIn: 'root' })
export class Catalog {
  readonly rows = signal<CatalogRow[]>([]);

  async load(): Promise<void> {
    try {
      const resp = await fetch('/item-names.json', { credentials: 'same-origin' });
      if (!resp.ok) return;
      const data: unknown = await resp.json();
      if (!Array.isArray(data)) return;
      this.rows.set(
        data.filter(
          (r): r is CatalogRow =>
            Array.isArray(r) && r.length === 5 && r.every((x) => typeof x === 'string'),
        ),
      );
    } catch {
      // no catalogue: typing internal names still works
    }
  }
}
