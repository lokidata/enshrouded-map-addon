import { Component, inject, signal } from '@angular/core';
import { Api } from '../core/api';
import { Confirm } from '../core/confirm';
import { fmtDate, fmtSize } from '../core/format';
import { I18n, T } from '../core/i18n';
import { NAVIGATE } from '../core/navigate';
import { failure } from '../core/reasons';
import { Backup, ServerData } from '../core/server-data';
import { Session } from '../core/session';

/** The backup list; level action can create one and download a finished one. */
@Component({
  imports: [T],
  selector: 'app-backups',
  template: `
    @if (session.canAct('server')) {
      <p>
        <button type="button" [disabled]="busy()" (click)="create()">
          {{ 'backups.create' | t }}
        </button>
      </p>
    }
    <p role="status">{{ message() }}</p>
    <p role="alert" class="err">{{ error() || data.backupsError() }}</p>
    <div class="scroll" tabindex="0" role="region" [attr.aria-label]="'sec.backups' | t">
      <table class="entries-table">
        <thead>
          <tr>
            <th>{{ 'backups.name' | t }}</th>
            <th>{{ 'backups.size' | t }}</th>
            <th>{{ 'backups.date' | t }}</th>
            <th>{{ 'backups.status' | t }}</th>
            <th>
              <span class="sr">{{ 'backups.action' | t }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          @for (b of data.backups(); track b.uuid) {
            <tr>
              <td>{{ b.name }}</td>
              <td>{{ size(b.bytes) }}</td>
              <td>{{ date(b.created_at) }}</td>
              <td>{{ label(b) }}</td>
              <td>
                @if (session.canAct('server') && ready(b)) {
                  <button type="button" class="dl" [disabled]="busy()" (click)="download(b)">
                    {{ 'backups.download' | t }}
                  </button>
                }
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class Backups {
  private readonly api = inject(Api);
  private readonly confirm = inject(Confirm);
  private readonly navigate = inject(NAVIGATE);
  private readonly i18n = inject(I18n);
  protected readonly session = inject(Session);
  protected readonly data = inject(ServerData);
  protected readonly busy = signal(false);
  protected readonly message = signal('');
  protected readonly error = signal('');
  protected readonly size = (n: number) => fmtSize(n, this.i18n.t);
  protected readonly date = (iso: string) => fmtDate(iso, this.i18n.locale());

  protected label(b: Backup): string {
    const t = this.i18n.t;
    return b.completed_at === null
      ? t('backups.running')
      : b.is_successful === false
        ? t('backups.failed')
        : '';
  }

  protected ready(b: Backup): boolean {
    return b.completed_at !== null && b.is_successful === true;
  }

  protected async create(): Promise<void> {
    const t = this.i18n.t;
    const filtered = this.session.me()?.backup_filtered;
    if (!filtered) {
      // no BACKUP_IGNORED: the backup holds every file of the server and can be very large
      const yes = await this.confirm.ask({
        title: t('backups.full.title'),
        label: t('backups.full.label'),
      });
      if (!yes) return;
    }
    await this.run(
      () => this.api.post('/backups', filtered ? {} : { confirm_full: true }),
      t('backups.started'),
    );
  }

  protected async download(b: Backup): Promise<void> {
    await this.run(async () => {
      const { url } = await this.api.post<{ url: string }>(`/backups/${b.uuid}/download`, {});
      this.navigate(url); // one-time signed URL: the browser downloads from the node
    }, '');
  }

  private async run(call: () => Promise<unknown>, ok: string): Promise<void> {
    this.busy.set(true);
    this.message.set('');
    this.error.set('');
    try {
      await call();
      this.message.set(ok);
    } catch (err) {
      this.error.set(failure(err, this.i18n.t));
    }
    this.busy.set(false);
    await this.data.reloadAfterAction();
  }
}
