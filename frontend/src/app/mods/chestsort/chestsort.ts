import { Component, computed, inject, signal } from '@angular/core';
import { Api } from '../../core/api';
import { Confirm } from '../../core/confirm';
import { I18n, T } from '../../core/i18n';
import { Session } from '../../core/session';
import {
  addCategory,
  Cats,
  csFailure,
  deleteCategory,
  filterItems,
  lines,
  Preview,
  previewText,
  renameCategory,
} from './chestsort.logic';

/** The chestsort categories editor. The edited state lives in memory only. */
@Component({
  imports: [T],
  selector: 'app-chestsort',
  template: `
    <p role="status">{{ message() }}</p>
    <p role="alert" class="err pre">{{ error() }}</p>
    @if (stale()) {
      <p>
        <button type="button" class="btn" (click)="load()">{{ 'cs.reload' | t }}</button>
      </p>
    }
    <p>
      <label for="cs-list">{{ 'cs.categories' | t }}</label><br />
      <select id="cs-list" size="8" (change)="select($event)">
        @for (n of names(); track n) {
          <option [value]="n" [selected]="n === selected()">{{ n }}</option>
        }
      </select>
    </p>
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
        <button type="button" class="btn" (click)="add()">{{ 'cs.add' | t }}</button>
        <button type="button" class="btn" (click)="rename()">{{ 'cs.rename' | t }}</button>
        <button type="button" class="btn" (click)="remove()">{{ 'cs.delete' | t }}</button>
      </p>
    }
    <p>
      <label for="cs-words">{{ 'cs.words' | t }}</label>
      <output>{{ 'cs.words_n' | t: { n: wordCount() } }}</output><br />
      <textarea
        id="cs-words"
        rows="5"
        spellcheck="false"
        [disabled]="selected() === null"
        [readOnly]="!edit()"
        [value]="wordsText()"
        (input)="editWords($event)"
      ></textarea>
    </p>
    <p>
      <label for="cs-items">{{ 'cs.items' | t }}</label> <output>{{ itemsLabel() }}</output><br />
      <label for="cs-filter">{{ 'cs.filter' | t }}</label>
      <input type="search" id="cs-filter" [value]="filter()" (input)="setFilter($event)" /><br />
      <textarea
        id="cs-items"
        rows="12"
        spellcheck="false"
        [disabled]="selected() === null"
        [readOnly]="!edit() || filter().trim() !== ''"
        [value]="itemsText()"
        (input)="editItems($event)"
      ></textarea>
    </p>
    @if (edit()) {
      <p class="row">
        <button type="button" class="btn" (click)="preview()">{{ 'cs.preview' | t }}</button>
        <button type="button" class="btn primary" [disabled]="!previewed()" (click)="save()">
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
        <button
          type="button"
          class="btn"
          [disabled]="backups().length === 0"
          (click)="restore(bak.value)"
        >
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
  protected readonly edit = inject(Session).canAct;

  protected readonly cats = signal<Cats>({});
  private hash = '';
  protected readonly selected = signal<string | null>(null);
  protected readonly name = signal('');
  protected readonly filter = signal('');
  // the textareas keep what was typed: they are rewritten only when the selection or the filter changes
  protected readonly wordsText = signal('');
  protected readonly itemsText = signal('');
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
      ? t('cs.items_filtered', { shown: filterItems(this.current().items, q).length, n })
      : t('cs.items_n', { n });
  });

  constructor() {
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
    this.itemsText.set(this.current().items.join('\n'));
  }

  protected select(e: Event): void {
    this.fill(this.val(e));
  }

  protected setFilter(e: Event): void {
    this.filter.set(this.val(e));
    this.itemsText.set(filterItems(this.current().items, this.filter()).join('\n'));
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

  protected editItems(e: Event): void {
    if (this.edit() && this.filter().trim() === '') this.patch({ items: lines(this.val(e)) });
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
