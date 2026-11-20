import { Injectable, inject, signal } from '@angular/core';
import { Api } from './api';
import { I18n, Translate } from './i18n';
import { Key } from './lang.fr';
import { failure } from './reasons';

export interface ServerStatus {
  name: string;
  state: string;
  cpu: number;
  memory_bytes: number;
  disk_bytes: number;
  uptime_ms: number;
}

const STATES = new Set(['running', 'offline', 'starting', 'stopping', 'unknown']);

/** The state in the language of the page; a state this UI does not know is shown as it came. */
export const stateLabel = (state: string, t: Translate): string =>
  STATES.has(state) ? t(`state.${state}` as Key) : state;

const POLL_MS = 15000;

/** The game server's state, polled while the tab is visible; `unknown` after a failed read. */
@Injectable({ providedIn: 'root' })
export class Status {
  private readonly api = inject(Api);
  private readonly i18n = inject(I18n);
  private pending: Promise<void> | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  readonly state = signal('unknown');
  readonly info = signal<ServerStatus | null>(null);
  readonly error = signal('');

  /** One request at a time: callers during a read share its result. */
  refresh(): Promise<void> {
    this.pending ??= this.read().finally(() => (this.pending = null));
    return this.pending;
  }

  tick(): Promise<void> {
    return document.hidden ? Promise.resolve() : this.refresh();
  }

  start(): void {
    this.stop();
    void this.refresh();
    this.timer = setInterval(() => void this.tick(), POLL_MS);
    document.addEventListener('visibilitychange', this.onVisible);
  }

  /** Off: no polling (the screen is hidden); on: a read now, then the poll again. */
  setActive(on: boolean): void {
    if (on) this.start();
    else this.stop();
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
    document.removeEventListener('visibilitychange', this.onVisible);
  }

  private readonly onVisible = () => void this.tick();

  private async read(): Promise<void> {
    try {
      const s = await this.api.get<ServerStatus>('/status');
      this.info.set(s);
      this.state.set(s.state);
      this.error.set('');
    } catch (err) {
      this.state.set('unknown'); // unknown: no power button until a read succeeds
      this.error.set(failure(err, this.i18n.t));
    }
  }
}
