import { Component, effect, inject, input } from '@angular/core';
import { ApiBase } from '../core/api';
import { I18n, T } from '../core/i18n';
import { Session } from '../core/session';
import { ConfirmDialog } from '../ui/confirm-dialog';
import { Section } from '../ui/section';
import { Chestsort } from './chestsort/chestsort';
import { ModsAboutDe } from './mods-about-de';
import { ModsAboutEn } from './mods-about-en';
import { ModsAboutFr } from './mods-about-fr';

/** The `chestsort` add-on: what the installed mods do (open), then the chestsort categories editor (closed). */
@Component({
  imports: [T, ConfirmDialog, Section, Chestsort, ModsAboutFr, ModsAboutEn, ModsAboutDe],
  selector: 'app-mods',
  template: `
    @if (!session.loaded()) {
      <p role="status">{{ 'common.loading' | t }}</p>
    } @else if (session.error()) {
      <p role="alert" class="err">{{ session.error() }}</p>
    } @else if (!session.hasAccess('chestsort')) {
      <p role="alert" class="err">{{ 'common.no_access' | t }}</p>
    } @else {
      <app-section [heading]="'sec.mods' | t" storageKey="mods-about" [open]="true">
        @switch (i18n.lang()) {
          @case ('fr') {
            <app-mods-about-fr />
          }
          @case ('de') {
            <app-mods-about-de />
          }
          @default {
            <app-mods-about-en />
          }
        }
      </app-section>
      @if (session.me()?.chestsort) {
        <app-section [heading]="'sec.chestsort' | t" storageKey="mods-chestsort">
          <app-chestsort />
        </app-section>
      }
    }
    <app-confirm-dialog />
  `,
})
export class Mods {
  protected readonly session = inject(Session);
  protected readonly i18n = inject(I18n);
  /** Set by the site on the element. */
  readonly lang = input('fr');
  /** The public base of this add-on (`/addon/<key>/`), set by the site; checked by ApiBase. */
  readonly base = input<string>();
  private readonly apiBase = inject(ApiBase);

  constructor() {
    effect(() => this.i18n.setLang(this.lang()));
    effect(() => this.apiBase.set(this.base()));
  }
}
