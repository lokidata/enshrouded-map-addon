import { Component, inject } from '@angular/core';
import { I18n, T } from '../core/i18n';
import { Session } from '../core/session';
import { Section } from '../ui/section';
import { Chestsort } from './chestsort/chestsort';
import { ModsAboutEn } from './mods-about-en';
import { ModsAboutFr } from './mods-about-fr';

/** Page Mods: what the installed mods do (open), then the chestsort categories editor (closed). */
@Component({
  imports: [T, Section, Chestsort, ModsAboutFr, ModsAboutEn],
  selector: 'app-mods',
  template: `
    @if (!session.loaded()) {
      <p role="status">{{ 'common.loading' | t }}</p>
    } @else if (session.error()) {
      <p role="alert" class="err">{{ session.error() }}</p>
    } @else if (!session.hasAccess()) {
      <p role="alert" class="err">{{ 'common.no_access' | t }}</p>
    } @else {
      <app-section [heading]="'sec.mods' | t" storageKey="mods-about" [open]="true">
        @if (i18n.lang() === 'fr') {
          <app-mods-about-fr />
        } @else {
          <app-mods-about-en />
        }
      </app-section>
      @if (session.me()?.chestsort) {
        <app-section [heading]="'sec.chestsort' | t" storageKey="mods-chestsort">
          <app-chestsort />
        </app-section>
      }
    }
  `,
})
export class Mods {
  protected readonly session = inject(Session);
  protected readonly i18n = inject(I18n);
}
