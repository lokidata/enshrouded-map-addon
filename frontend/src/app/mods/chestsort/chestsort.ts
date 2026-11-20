import { Component, computed, inject, signal } from '@angular/core';
import { Api } from '../../core/api';
import { ItemPicker } from './item-picker';
import { Catalog, iconOf, nameOf } from '../../core/catalog';
import { Confirm } from '../../core/confirm';
import { I18n, T } from '../../core/i18n';
import { Session } from '../../core/session';
import {
  addCategory,
  addItems,
  Cats,
  Conflict,
  csFailure,
  deleteCategory,
  duplicates,
  filterItems,
  prettyName,
  lines,
  moveItems,
  parseNames,
  Preview,
  previewText,
  removeItem,
  renameCategory,
} from './chestsort.logic';

const SHOWN = 200; // chips drawn at once: a category may hold thousands of items

/** The chestsort categories editor. The edited state lives in memory only. */
@Component({
  imports: [T, ItemPicker],
  selector: 'app-chestsort',
  template: `
    <p role="status">{{ message() }}</p>
    <p role="alert" class="err pre">{{ error() }}</p>
    @if (stale()) {
      <p>
        <button type="button" (click)="load()">{{ 'cs.reload' | t }}</button>
      </p>
    }
    <p id="cs-cats-label" class="cs-label">{{ 'cs.categories' | t }}</p>
    <ul class="cs-cats" aria-labelledby="cs-cats-label">
      @for (n of names(); track n) {
        <li>
          <button
            type="button"
            class="cs-cat"
            [attr.aria-pressed]="n === selected()"
            (click)="choose(n)"
          >
            {{ n }}
          </button>
        </li>
      }
    </ul>
    @if (edit()) {
      <p class="row">
        <label for="cs-name">{{ 'cs.name' | t }}</label>
        <input
          type="text"
          id="cs-name"
          maxlength="60"
          [value]="name()"
          (input)="name.set(val($event))"
        />
        <button type="button" (click)="add()">{{ 'cs.add' | t }}</button>
        <button type="button" (click)="rename()">{{ 'cs.rename' | t }}</button>
        <button type="button" (click)="remove()">{{ 'cs.delete' | t }}</button>
      </p>
    }
    <div class="cs-grid">
      <div class="cs-main">
        <p class="cs-words">
          <label for="cs-words">{{ 'cs.words' | t }}</label>
          <output>{{ 'cs.words_n' | t: { n: wordCount() } }}</output><br />
          <textarea
            id="cs-words"
            rows="4"
            spellcheck="false"
            [disabled]="selected() === null"
            [readOnly]="!edit()"
            [value]="wordsText()"
            (input)="editWords($event)"
          ></textarea>
        </p>
        <h3>
          {{ 'cs.items' | t }} <output>{{ itemsLabel() }}</output>
        </h3>
        @if (dupText()) {
          <p role="alert" class="err">{{ dupText() }}</p>
        }
        <p>
          <label for="cs-filter">{{ 'cs.filter' | t }}</label>
          <input
            type="search"
            id="cs-filter"
            [value]="filter()"
            (input)="filter.set(val($event))"
          />
        </p>
        @if (edit()) {
          @if (catalog.rows().length) {
            <p>
              <button type="button" [disabled]="selected() === null" (click)="picking.set(true)">
                {{ 'cs.pick_open' | t }}
              </button>
            </p>
            <app-item-picker
              [(open)]="picking"
              [rows]="catalog.rows()"
              [category]="selected() ?? ''"
              [owners]="owners()"
              (pick)="pickItem($event)"
            />
          } @else {
            <p>
              <label for="cs-add">{{ 'cs.item_label' | t }}</label><br />
              <textarea
                id="cs-add"
                rows="2"
                spellcheck="false"
                [disabled]="selected() === null"
                [value]="draft()"
                (input)="draft.set(val($event))"
                (keydown.enter)="enter($event)"
              ></textarea>
              <button type="button" [disabled]="selected() === null" (click)="addDraft()">
                {{ 'cs.item_add' | t }}
              </button>
            </p>
            <p class="hint">{{ 'cs.item_help' | t }}</p>
            @if (known().length) {
              <ul class="cs-suggest" [attr.aria-label]="'cs.known' | t">
                @for (k of known(); track k.item) {
                  <li>
                    <button type="button" (click)="suggest(k.item)">
                      @if (k.icon) {
                        <img [src]="k.icon" alt="" width="20" height="20" />
                      }
                      {{ k.label }}
                      @if (k.from) {
                        · {{ k.from }}
                      }
                    </button>
                  </li>
                }
              </ul>
            }
          }
        }
        <p role="status">{{ notice() }}</p>
        @if (pending().length) {
          <div class="cs-conflicts" role="group" [attr.aria-label]="'cs.move' | t">
            @for (c of pending(); track c.item) {
              <p>
                {{ 'cs.conflict' | t: { item: c.item, from: c.from } }}
                <button type="button" (click)="move([c])">{{ 'cs.move' | t }}</button>
              </p>
            }
            @if (pending().length > 1) {
              <button type="button" (click)="move(pending())">{{ 'cs.move_all' | t }}</button>
            }
            <button type="button" (click)="pending.set([])">{{ 'cs.skip' | t }}</button>
          </div>
        }
        @if (shown().length) {
          <ul class="cs-tiles" [attr.aria-label]="'cs.items' | t">
            @for (i of shown(); track i) {
              <li class="cs-tile">
                @if (labels().get(i.toLowerCase()); as l) {
                  @if (l.icon) {
                    <img [src]="l.icon" alt="" width="36" height="36" />
                  } @else {
                    <span class="cs-noicon" aria-hidden="true"></span>
                  }
                  <span [attr.title]="i">{{ l.label }}</span>
                } @else {
                  <span class="cs-noicon" aria-hidden="true"></span>
                  <span class="cs-unnamed" [attr.title]="i">{{ pretty(i) }}</span>
                }
                @if (edit()) {
                  <button
                    type="button"
                    class="cs-x"
                    [attr.aria-label]="
                      'cs.item_remove' | t: { name: labels().get(i.toLowerCase())?.label ?? i }
                    "
                    (click)="drop(i)"
                  >
                    ✕
                  </button>
                }
              </li>
            }
          </ul>
        } @else {
          <p class="empty">{{ 'cs.item_none' | t }}</p>
        }
        @if (more() > 0) {
          <p class="meta">{{ 'cs.item_more' | t: { n: more() } }}</p>
        }
      </div>
    </div>
    <p class="row">
      <button type="button" (click)="download()">{{ 'cs.download' | t }}</button>
      @if (edit()) {
        <button type="button" (click)="file.click()">{{ 'cs.import' | t }}</button>
        <input #file type="file" accept=".json,application/json" hidden (change)="importFile($event)" />
      }
    </p>
    @if (edit()) {
      <p class="row">
        <button type="button" (click)="preview()">{{ 'cs.preview' | t }}</button>
        <button type="button" class="primary" [disabled]="!previewed()" (click)="save()">
          {{ 'cs.save' | t }}
        </button>
      </p>
    }
    <pre tabindex="0" [attr.aria-label]="'cs.preview' | t">{{ diff() }}</pre>
    @if (edit()) {
      <p class="row">
        <label for="cs-bak">{{ 'cs.restore_label' | t }}</label>
        <select id="cs-bak" #bak>
          @for (b of backups(); track b) {
            <option [value]="b">{{ b }}</option>
          }
        </select>
        <button type="button" [disabled]="backups().length === 0" (click)="restore(bak.value)">
          {{ 'cs.restore' | t }}
        </button>
      </p>
    }
  `,
})
export class Chestsort {
  private readonly api = inject(Api);
  private readonly confirm = inject(Confirm);
  private readonly i18n = inject(I18n);
  private readonly session = inject(Session);
  protected readonly catalog = inject(Catalog);
  protected readonly picking = signal(false);
  protected readonly pretty = prettyName;
  protected readonly edit = computed(() => this.session.canAct('chestsort'));

  protected readonly cats = signal<Cats>({});
  private hash = '';
  protected readonly selected = signal<string | null>(null);
  protected readonly name = signal('');
  protected readonly filter = signal('');
  // the words box keeps what was typed: it is rewritten only when the selection changes
  protected readonly wordsText = signal('');
  protected readonly draft = signal('');
  protected readonly notice = signal('');
  protected readonly pending = signal<Conflict[]>([]);
  protected readonly previewed = signal(false);
  protected readonly diff = signal('');
  protected readonly message = signal('');
  protected readonly error = signal('');
  protected readonly stale = signal(false);
  protected readonly backups = signal<string[]>([]);
  // bumped by every edit, so a preview answer for older content is dropped
  private version = 0;

  protected readonly names = computed(() => Object.keys(this.cats()));
  private readonly current = computed(
    () => this.cats()[this.selected() ?? ''] ?? { words: [], items: [] },
  );
  protected readonly wordCount = computed(() => this.current().words.length);
  protected readonly itemsLabel = computed(() => {
    const n = this.current().items.length;
    const q = this.filter().trim();
    const t = this.i18n.t;
    return q
      ? t('cs.items_filtered', {
          shown: filterItems(this.current().items, q, this.shownName).length,
          n,
        })
      : t('cs.items_n', { n });
  });

  private readonly matches = computed(() =>
    filterItems(this.current().items, this.filter(), this.shownName),
  );
  protected readonly shown = computed(() => this.matches().slice(0, SHOWN));
  protected readonly more = computed(() => this.matches().length - this.shown().length);
  /** Without a catalogue: names already used in other categories that contain the draft. */
  /** lower-case item name → the category holding it */
  protected readonly owners = computed(() => {
    const owners = new Map<string, string>();
    for (const [n, c] of Object.entries(this.cats()))
      for (const i of c.items) owners.set(i.toLowerCase(), n);
    return owners;
  });
  /** Without a catalogue: names already used in other categories that contain the draft. */
  protected readonly known = computed(() => {
    const sel = this.selected();
    const q = this.draft().trim().toLowerCase();
    if (q.length < 2) return [];
    const out: { item: string; label: string; icon: null; from: string }[] = [];
    for (const [n, c] of Object.entries(this.cats()))
      for (const i of n === sel ? [] : c.items) {
        if (i.toLowerCase().includes(q)) out.push({ item: i, label: i, icon: null, from: n });
        if (out.length >= 8) return out;
      }
    return out;
  });
  /** What the user reads for an item: its name in his language, else the internal name. */
  private readonly shownName = (item: string): string =>
    this.labels().get(item.toLowerCase())?.label ?? prettyName(item);
  /** Name and picture of an internal name, when the catalogue knows it. */
  protected readonly labels = computed(() => {
    const lang = this.i18n.lang();
    return new Map(
      this.catalog
        .rows()
        .map((r) => [r[0].toLowerCase(), { label: nameOf(r, lang), icon: iconOf(r) }]),
    );
  });
  protected readonly dupText = computed(() => {
    const d = duplicates(this.cats());
    return d.length
      ? this.i18n.t('cs.dups', {
          list:
            d
              .slice(0, 5)
              .map((e) => `${e.item} (${e.cats.join(', ')})`)
              .join('; ') + (d.length > 5 ? ` +${d.length - 5}` : ''),
        })
      : '';
  });

  constructor() {
    void this.catalog.load();
    void this.load();
  }

  protected val(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }

  protected async load(): Promise<void> {
    this.fail('');
    try {
      const data = await this.api.get<{ categories: Cats; hash: string }>('/chestsort');
      this.cats.set(data.categories);
      this.hash = data.hash;
      this.dirty();
      this.fill(this.selected());
    } catch (err) {
      this.fail(csFailure(err, this.i18n.t), err);
    }
    if (this.edit()) void this.loadBackups();
  }

  private async loadBackups(): Promise<void> {
    try {
      this.backups.set(await this.api.get<string[]>('/chestsort/backups'));
    } catch (err) {
      this.fail(csFailure(err, this.i18n.t), err);
    }
  }

  private fail(text: string, err?: unknown): void {
    this.error.set(text);
    this.stale.set((err as { detail?: string } | undefined)?.detail === 'changed_elsewhere');
  }

  private dirty(): void {
    this.version++;
    this.previewed.set(false);
    this.diff.set('');
  }

  /** Select a category (or the first one) and rewrite the editors. */
  private fill(keep: string | null): void {
    const names = Object.keys(this.cats());
    this.selected.set(keep !== null && keep in this.cats() ? keep : (names[0] ?? null));
    this.name.set(this.selected() ?? '');
    this.wordsText.set(this.current().words.join('\n'));
    this.filter.set('');
    this.draft.set('');
    this.notice.set('');
    this.pending.set([]);
  }

  protected choose(name: string): void {
    this.fill(name);
  }

  private patch(change: Partial<{ words: string[]; items: string[] }>): void {
    const sel = this.selected();
    if (sel === null) return;
    this.cats.update((c) => ({ ...c, [sel]: { ...c[sel], ...change } }));
    this.dirty();
  }

  protected editWords(e: Event): void {
    if (this.edit()) this.patch({ words: lines(this.val(e)) });
  }

  /** Enter adds; Shift+Enter is a new line (several names at once). */
  protected enter(e: Event): void {
    if ((e as KeyboardEvent).shiftKey) return;
    e.preventDefault();
    this.addDraft();
  }

  protected suggest(item: string): void {
    this.draft.set(item);
    this.addDraft();
  }

  protected addDraft(): void {
    const sel = this.selected();
    if (!this.edit() || sel === null) return;
    const names = parseNames(this.draft());
    if (!names.length) return;
    const r = addItems(this.cats(), sel, names);
    const t = this.i18n.t;
    const note: string[] = [];
    if (r.added.length) {
      this.cats.set(r.cats);
      this.dirty();
      note.push(t('cs.item_added', { names: r.added.join(', ') }));
    }
    if (r.present.length) note.push(t('cs.item_present', { names: r.present.join(', ') }));
    if (r.invalid.length) note.push(t('cs.item_invalid'));
    this.notice.set(note.join(' '));
    this.pending.set(r.conflicts);
    this.draft.set('');
  }

  /** A row of the picker: add the item, or move it here when another category holds it. */
  protected pickItem(item: string): void {
    const sel = this.selected();
    const from = this.owners().get(item.toLowerCase());
    if (!this.edit() || sel === null || from === sel) return;
    if (from) this.cats.set(moveItems(this.cats(), sel, [{ item, from }]));
    else this.cats.set(addItems(this.cats(), sel, [item]).cats);
    this.dirty();
  }

  protected move(conflicts: Conflict[]): void {
    const sel = this.selected();
    if (!this.edit() || sel === null) return;
    this.cats.set(moveItems(this.cats(), sel, conflicts));
    this.pending.update((p) => p.filter((c) => !conflicts.includes(c)));
    this.dirty();
  }

  protected drop(item: string): void {
    const sel = this.selected();
    if (!this.edit() || sel === null) return;
    this.cats.set(removeItem(this.cats(), sel, item));
    this.dirty();
  }

  protected add(): void {
    const r = addCategory(this.cats(), this.name());
    if ('error' in r) return this.fail(this.i18n.t(r.error));
    this.fail('');
    this.cats.set(r.cats);
    this.dirty();
    this.fill(this.name().trim());
  }

  protected rename(): void {
    const sel = this.selected();
    if (sel === null) return;
    const r = renameCategory(this.cats(), sel, this.name());
    if (!r) return;
    if ('error' in r) return this.fail(this.i18n.t(r.error));
    this.fail('');
    this.cats.set(r.cats);
    this.dirty();
    this.fill(this.name().trim());
  }

  protected async remove(): Promise<void> {
    const sel = this.selected();
    if (sel === null) return;
    const yes = await this.confirm.ask({
      title: this.i18n.t('cs.del.title', { name: sel }),
      label: this.i18n.t('cs.del.label'),
    });
    if (!yes) return;
    this.cats.set(deleteCategory(this.cats(), sel));
    this.dirty();
    this.fill(null);
  }

  /** The file as a save would write it (the server keeps `_readme` and the other keys), saved by the browser. */
  protected async download(): Promise<void> {
    this.fail('');
    try {
      const r = await this.api.post<{ name: string; text: string }>('/chestsort/export', {
        categories: this.cats(),
      });
      const url = URL.createObjectURL(new Blob([r.text], { type: 'application/json' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = r.name;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      this.fail(csFailure(err, this.i18n.t), err);
    }
  }

  /** Loads a local file into the editor; nothing is sent until the usual preview, confirmation and save. */
  protected async importFile(e: Event): Promise<void> {
    const input = e.target as HTMLInputElement;
    const f = input.files?.[0];
    input.value = '';
    if (!f || !this.edit()) return;
    this.fail('');
    try {
      const raw = JSON.parse(await f.text()) as { categories?: unknown };
      const cats = raw?.categories;
      if (typeof cats !== 'object' || cats === null || Array.isArray(cats)) throw new Error();
      this.cats.set(cats as Cats); // the add-on's preview checks the content
      this.dirty();
      this.fill(null);
    } catch {
      this.fail(this.i18n.t('cs.import_bad'));
    }
  }

  protected async preview(): Promise<void> {
    this.fail('');
    this.message.set('');
    const version = this.version;
    try {
      const r = await this.api.post<Preview>('/chestsort/preview', { categories: this.cats() });
      if (version !== this.version) return; // edited meanwhile: this diff is not the current content
      this.diff.set(previewText(r, this.i18n.t));
      this.previewed.set(r.errors.length === 0 && r.changed);
    } catch (err) {
      this.fail(csFailure(err, this.i18n.t), err);
    }
  }

  protected async save(): Promise<void> {
    const yes = await this.confirm.ask({
      title: this.i18n.t('cs.save.title'),
      label: this.i18n.t('cs.save.label'),
    });
    if (yes)
      await this.write(() =>
        this.api.put('/chestsort', {
          categories: this.cats(),
          base_hash: this.hash,
          confirm: true,
        }),
      );
  }

  protected async restore(name: string): Promise<void> {
    if (!name) return;
    const yes = await this.confirm.ask({
      title: this.i18n.t('cs.restore.title', { name }),
      label: this.i18n.t('cs.restore.label'),
    });
    if (yes)
      await this.write(() =>
        this.api.post('/chestsort/restore', { name, base_hash: this.hash, confirm: true }),
      );
  }

  private async write(run: () => Promise<unknown>): Promise<void> {
    this.fail('');
    this.message.set('');
    const was = this.previewed();
    this.previewed.set(false);
    try {
      const r = (await run()) as { backup: string; hash: string };
      this.message.set(this.i18n.t('cs.saved', { backup: r.backup }));
      this.hash = r.hash;
      await this.load();
    } catch (err) {
      this.fail(csFailure(err, this.i18n.t), err);
      this.previewed.set(was);
    }
  }
}
