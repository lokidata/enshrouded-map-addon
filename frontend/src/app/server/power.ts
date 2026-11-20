import { Component, inject, signal } from '@angular/core';
import { Api } from '../core/api';
import { Confirm } from '../core/confirm';
import { I18n } from '../core/i18n';
import { failure } from '../core/reasons';
import { ServerData } from '../core/server-data';
import { Status } from '../core/status';

type Signal = 'start' | 'stop' | 'restart';
const NEEDS: Record<Signal, string> = { start: 'offline', stop: 'running', restart: 'running' };

/** Start, stop and restart: each enabled only in the state it makes sense in. */
@Component({
  selector: 'app-power',
  template: `
    <div class="actions" role="group" [attr.aria-label]="group()">
      @for (s of signals; track s) {
        <button
          type="button"
          [class.danger]="s === 'stop'"
          [disabled]="!enabled(s)"
          (click)="run(s)"
        >
          {{ label(s) }}
        </button>
      }
    </div>
    <p role="status">{{ message() }}</p>
    <p role="alert" class="err">{{ error() }}</p>
  `,
})
export class Power {
  private readonly api = inject(Api);
  private readonly confirm = inject(Confirm);
  private readonly data = inject(ServerData);
  private readonly status = inject(Status);
  private readonly i18n = inject(I18n);
  protected readonly busy = signal(false);
  protected readonly message = signal('');
  protected readonly error = signal('');
  protected readonly signals: Signal[] = ['start', 'restart', 'stop'];

  protected group(): string {
    return this.i18n.t('sec.actions');
  }

  protected label(s: Signal): string {
    return this.i18n.t(`power.${s}`);
  }

  protected enabled(s: Signal): boolean {
    return !this.busy() && this.status.state() === NEEDS[s];
  }

  protected async run(s: Signal): Promise<void> {
    const t = this.i18n.t;
    if (s !== 'start') {
      const yes = await this.confirm.ask({
        title: t(s === 'stop' ? 'power.title.stop' : 'power.title.restart'),
        label: t('confirm.warned'),
      });
      if (!yes) return;
    }
    this.busy.set(true);
    this.message.set('');
    this.error.set('');
    try {
      await this.api.post('/power', s === 'start' ? { signal: s } : { signal: s, confirm: true });
      this.message.set(t(`power.done.${s}`));
    } catch (err) {
      this.error.set(failure(err, t));
    }
    this.busy.set(false);
    await this.data.reloadAfterAction();
  }
}
