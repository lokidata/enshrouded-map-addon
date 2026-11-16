import { Component, ElementRef, effect, inject, signal, viewChild } from '@angular/core';
import { Confirm } from '../core/confirm';
import { T } from '../core/i18n';

/** The one modal of the page: a title, a sentence to tick, OK only once ticked. */
@Component({
  imports: [T],
  selector: 'app-confirm-dialog',
  template: `
    <dialog #dlg class="plate" aria-labelledby="c-title" (close)="dismiss()">
      @if (request(); as r) {
        <h2 id="c-title">{{ r.title }}</h2>
        <p>
          <input type="checkbox" id="c-warned" #box (change)="ticked.set(box.checked)" />
          <label for="c-warned">{{ r.label }}</label>
        </p>
        <p class="row">
          <button type="button" class="btn ok" [disabled]="!ticked()" (click)="r.done(true)">
            {{ 'confirm.ok' | t }}
          </button>
          <button type="button" class="btn cancel" (click)="r.done(false)">
            {{ 'confirm.cancel' | t }}
          </button>
        </p>
      }
    </dialog>
  `,
})
export class ConfirmDialog {
  protected readonly request = inject(Confirm).request;
  protected readonly ticked = signal(false);
  private readonly dlg = viewChild.required<ElementRef<HTMLDialogElement>>('dlg');

  constructor() {
    effect(() => {
      const dialog = this.dlg().nativeElement;
      if (this.request()) {
        this.ticked.set(false);
        if (!dialog.open) dialog.showModal();
      } else if (dialog.open) {
        dialog.close();
      }
    });
  }

  /** Escape closes the dialog without an answer: that is a no. */
  protected dismiss(): void {
    this.request()?.done(false);
  }
}
