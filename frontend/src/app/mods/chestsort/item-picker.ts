import {
  Component,
  ElementRef,
  computed,
  effect,
  inject,
  input,
  model,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { CatalogRow, iconOf, nameOf } from '../../core/catalog';
import { I18n, T } from '../../core/i18n';

const SHOWN = 100;

/**
 * A popup to browse the game's items by name and add them to the open category: search box, one row
 * per item (picture, name, where it is now) with an Add or Move button. It stays open to add several.
 */
@Component({
  selector: 'app-item-picker',
  imports: [T],
  template: `
    <dialog #dlg class="cs-pick" aria-labelledby="pick-title" (close)="open.set(false)">
      <header>
        <h2 id="pick-title">{{ 'cs.pick_title' | t: { name: category() } }}</h2>
        <button
          type="button"
          class="cs-x"
          [attr.aria-label]="'cs.pick_close' | t"
          (click)="open.set(false)"
        >
          ✕
        </button>
      </header>
      <label for="pick-q">{{ 'cs.pick_search' | t }}</label>
      <input
        id="pick-q"
        type="search"
        autocomplete="off"
        spellcheck="false"
        [value]="query()"
        (input)="query.set(val($event))"
      />
      @if (shown().length) {
        <ul class="cs-pick-list">
          @for (r of shown(); track r.item) {
            <li>
              @if (r.icon) {
                <img [src]="r.icon" alt="" width="40" height="40" />
              } @else {
                <span class="cs-pick-noicon" aria-hidden="true"></span>
              }
              <span class="cs-pick-name">
                {{ r.label }}
                <small>
                  @if (r.here) {
                    {{ 'cs.pick_here' | t }}
                  } @else if (r.owner) {
                    {{ 'cs.pick_in' | t: { cat: r.owner } }}
                  }
                </small>
              </span>
              @if (!r.here) {
                <button
                  type="button"
                  [attr.aria-label]="(r.owner ? 'cs.pick_move' : 'cs.pick_add') | t"
                  [attr.title]="r.label"
                  (click)="pick.emit(r.item)"
                >
                  {{ (r.owner ? 'cs.pick_move' : 'cs.pick_add') | t }}
                </button>
              }
            </li>
          }
        </ul>
      } @else {
        <p class="empty">{{ 'cs.pick_none' | t }}</p>
      }
      <footer role="status">
        {{ 'cs.pick_count' | t: { shown: shown().length, n: total() } }}
      </footer>
    </dialog>
  `,
})
export class ItemPicker {
  readonly open = model(false);
  readonly rows = input.required<readonly CatalogRow[]>();
  readonly category = input('');
  /** lower-case internal name → category that holds it (also searched) */
  readonly owners = input.required<ReadonlyMap<string, string>>();
  /** an item picked: the parent adds it, or moves it when another category holds it */
  readonly pick = output<string>();

  private readonly i18n = inject(I18n);
  private readonly dlg = viewChild.required<ElementRef<HTMLDialogElement>>('dlg');
  protected readonly query = signal('');

  private readonly found = computed(() => {
    const lang = this.i18n.lang();
    const q = this.query().trim().toLowerCase();
    const first: CatalogRow[] = [];
    const rest: CatalogRow[] = [];
    for (const r of this.rows()) {
      const at = q ? nameOf(r, lang).toLowerCase().indexOf(q) : 0;
      if (at === 0) first.push(r);
      else if (at > 0) rest.push(r);
      // the category holding the item matches too ("armes" lists the items of Armes)
      else if ((this.owners().get(r[0].toLowerCase()) ?? '').toLowerCase().includes(q))
        rest.push(r);
    }
    const byName = (a: CatalogRow, b: CatalogRow) =>
      nameOf(a, lang).localeCompare(nameOf(b, lang), lang);
    return first.sort(byName).concat(rest.sort(byName));
  });
  protected readonly total = computed(() => this.found().length);
  protected readonly shown = computed(() => {
    const lang = this.i18n.lang();
    const category = this.category();
    return this.found()
      .slice(0, SHOWN)
      .map((r) => {
        const owner = this.owners().get(r[0].toLowerCase()) ?? '';
        return {
          item: r[0],
          label: nameOf(r, lang),
          icon: iconOf(r),
          owner,
          here: owner !== '' && owner === category,
        };
      });
  });

  constructor() {
    effect(() => {
      const dialog = this.dlg().nativeElement;
      if (this.open()) {
        // a dialog inside a hidden screen must not open
        if (!dialog.open && !dialog.closest('[hidden]')) {
          this.query.set('');
          dialog.showModal();
        }
      } else if (dialog.open) {
        dialog.close();
      }
    });
  }

  protected val(e: Event): string {
    return (e.target as HTMLInputElement).value;
  }
}
