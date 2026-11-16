import { Injectable, computed, inject, signal } from '@angular/core';
import { Api } from './api';
import { I18n } from './i18n';
import { failure } from './reasons';

export type Level = 'read' | 'action' | null;
export interface Me {
  username: string;
  is_admin: boolean;
  level: Level;
  backup_filtered: boolean;
  chestsort: boolean;
}

/** Who the visitor is for the add-on (level, administrator), loaded once per page. */
@Injectable({ providedIn: 'root' })
export class Session {
  private readonly api = inject(Api);
  private readonly i18n = inject(I18n);
  readonly me = signal<Me | null>(null);
  readonly error = signal('');
  readonly loaded = signal(false);
  readonly hasAccess = computed(() => this.me()?.level != null);
  readonly canAct = computed(() => this.me()?.level === 'action');

  async load(): Promise<void> {
    try {
      this.me.set(await this.api.get<Me>('/me'));
      this.error.set('');
    } catch (err) {
      this.me.set(null);
      this.error.set(failure(err, this.i18n.t));
    }
    this.loaded.set(true);
  }
}
