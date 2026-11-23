import { Component, effect, inject, input, untracked } from '@angular/core';
import { ApiBase } from '../core/api';
import { I18n, T } from '../core/i18n';
import { ServerData } from '../core/server-data';
import { Session } from '../core/session';
import { Status } from '../core/status';
import { ConfirmDialog } from '../ui/confirm-dialog';
import { Section } from '../ui/section';
import { Backups } from './backups';
import { Journal } from './journal';
import { Power } from './power';
import { StatusCard } from './status-card';

/** The `server` add-on: Pelican (open), journal (closed). */
@Component({
  imports: [T, ConfirmDialog, Section, StatusCard, Power, Backups, Journal],
  selector: 'app-server',
  template: `
    @if (!session.loaded()) {
      <p role="status">{{ 'common.loading' | t }}</p>
    } @else if (session.error()) {
      <p role="alert" class="err">{{ session.error() }}</p>
    } @else if (!session.hasAccess('server')) {
      <p role="alert" class="err">{{ 'common.no_access' | t }}</p>
    } @else {
      <app-section [heading]="'sec.pelican' | t" storageKey="server-pelican" [open]="true">
        @if (session.canAct('server')) {
          <div class="power-bar"><app-power /></div>
        }
        <app-status-card />
        <h3>{{ 'sec.backups' | t }}</h3>
        <app-backups />
      </app-section>
      <app-section [heading]="'sec.journal' | t" storageKey="server-journal">
        <app-journal />
      </app-section>
    }
    <app-confirm-dialog />
  `,
})
export class Server {
  protected readonly session = inject(Session);
  private readonly data = inject(ServerData);
  private readonly status = inject(Status);
  private readonly i18n = inject(I18n);
  /** Set by the site on the element: the language, and whether this screen is the one shown. */
  readonly lang = input('fr');
  /** The public base of this add-on (`/addon/<key>/`), set by the site; checked by ApiBase. */
  readonly base = input<string>();
  private readonly apiBase = inject(ApiBase);
  readonly active = input('true');

  constructor() {
    effect(() => this.i18n.setLang(this.lang()));
    effect(() => this.apiBase.set(this.base()));
    effect(() => {
      // the poll runs only for someone who may read the status, and only while the screen is shown
      const on = this.session.hasAccess('server') && this.active() !== 'false';
      untracked(() => this.status.setActive(on));
    });
    effect(() => {
      if (!this.session.hasAccess('server')) return;
      untracked(() => {
        void this.data.loadBackups();
        void this.data.loadJournal();
      });
    });
  }
}
