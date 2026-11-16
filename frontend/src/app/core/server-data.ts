import { Injectable, inject, signal } from '@angular/core';
import { Api } from './api';
import { I18n } from './i18n';
import { failure } from './reasons';
import { Status } from './status';

export interface Backup {
  uuid: string;
  name: string;
  bytes: number;
  created_at: string;
  completed_at: string | null;
  is_successful: boolean | null;
  is_locked: boolean;
}
export interface JournalRow {
  at: string;
  username: string;
  action: string;
  target: string;
  result: string;
}
export interface AccessRow {
  user_key: string;
  username: string;
  level: 'read' | 'action' | null;
}

/** Lists of the Serveur page (backups, journal, access) and their load errors. */
@Injectable({ providedIn: 'root' })
export class ServerData {
  private readonly api = inject(Api);
  private readonly i18n = inject(I18n);
  private readonly status = inject(Status);
  readonly backups = signal<Backup[]>([]);
  readonly backupsError = signal('');
  readonly journal = signal<JournalRow[]>([]);
  readonly journalError = signal('');
  readonly access = signal<AccessRow[]>([]);
  readonly accessError = signal('');

  async loadBackups(): Promise<void> {
    try {
      this.backups.set(await this.api.get<Backup[]>('/backups'));
      this.backupsError.set('');
    } catch (err) {
      this.backupsError.set(failure(err, this.i18n.t));
    }
  }

  async loadJournal(): Promise<void> {
    try {
      this.journal.set(await this.api.get<JournalRow[]>('/journal'));
      this.journalError.set('');
    } catch (err) {
      this.journalError.set(failure(err, this.i18n.t));
    }
  }

  async loadAccess(): Promise<void> {
    try {
      this.access.set(await this.api.get<AccessRow[]>('/access'));
      this.accessError.set('');
    } catch (err) {
      this.accessError.set(failure(err, this.i18n.t));
    }
  }

  /** After a write: the state, the backup list and the journal. */
  async reloadAfterAction(): Promise<void> {
    await Promise.all([this.status.refresh(), this.loadBackups(), this.loadJournal()]);
  }
}
