import { Component, effect, inject, untracked } from '@angular/core';
import { T } from '../core/i18n';
import { ServerData } from '../core/server-data';
import { Session } from '../core/session';
import { Section } from '../ui/section';
import { Access } from './access';
import { Backups } from './backups';
import { Journal } from './journal';
import { Power } from './power';
import { StatusCard } from './status-card';

/** Page Serveur: Pelican (open), journal and access (closed). */
@Component({
  imports: [T, Section, StatusCard, Power, Backups, Journal, Access],
  selector: 'app-server',
  template: `
    @if (!session.loaded()) {
      <p role="status">{{ 'common.loading' | t }}</p>
    } @else if (session.error()) {
      <p role="alert" class="err">{{ session.error() }}</p>
    } @else if (!session.hasAccess()) {
      <p role="alert" class="err">{{ 'common.no_access' | t }}</p>
    } @else {
      <app-section [heading]="'sec.pelican' | t" storageKey="server-pelican" [open]="true">
        @if (session.canAct()) {
          <div class="bar"><app-power /></div>
        }
        <app-status-card />
        <h3>{{ 'sec.backups' | t }}</h3>
        <app-backups />
      </app-section>
      <app-section [heading]="'sec.journal' | t" storageKey="server-journal">
        <app-journal />
      </app-section>
      @if (session.me()?.is_admin) {
        <app-section [heading]="'sec.access' | t" storageKey="server-access">
          <app-access />
        </app-section>
      }
    }
  `,
})
export class Server {
  protected readonly session = inject(Session);
  private readonly data = inject(ServerData);

  constructor() {
    effect(() => {
      if (!this.session.hasAccess()) return;
      untracked(() => {
        void this.data.loadBackups();
        void this.data.loadJournal();
        if (this.session.me()?.is_admin) void this.data.loadAccess();
      });
    });
  }
}
