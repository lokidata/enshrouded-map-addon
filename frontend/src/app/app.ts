import { Component, effect, inject, untracked } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { I18n, T } from './core/i18n';
import { Session } from './core/session';
import { Status, stateLabel } from './core/status';
import { ConfirmDialog } from './ui/confirm-dialog';

@Component({
  imports: [RouterOutlet, RouterLink, RouterLinkActive, ConfirmDialog, T],
  selector: 'app-root',
  templateUrl: './app.html',
})
export class App {
  private readonly session = inject(Session);
  protected readonly status = inject(Status);
  protected readonly i18n = inject(I18n);

  constructor() {
    void this.session.load();
    effect(() => {
      if (this.session.hasAccess()) untracked(() => this.status.start());
    });
    effect(() => (document.title = this.i18n.t('app.title')));
  }

  protected label(state: string): string {
    return stateLabel(state, this.i18n.t);
  }
}
