import { Component, inject } from '@angular/core';
import { fmtGo, fmtUptime } from '../core/format';
import { I18n, T } from '../core/i18n';
import { Status, stateLabel } from '../core/status';

/** The server's figures as tiles, like the panel's console page. */
@Component({
  imports: [T],
  selector: 'app-status-card',
  template: `
    <div class="tiles">
      @if (status.info(); as s) {
        <p class="tile">
          <span class="k">{{ 'status.name' | t }}</span> <span class="v">{{ s.name }}</span>
        </p>
      }
      <p class="tile">
        <span class="k">{{ 'status.state' | t }}</span>
        <span class="v" [class.up]="status.state() === 'running'">{{ label(status.state()) }}</span>
      </p>
      @if (status.info(); as s) {
        <p class="tile">
          <span class="k">{{ 'status.uptime' | t }}</span>
          <span class="v">{{ uptime(s.uptime_ms) }}</span>
        </p>
        <p class="tile">
          <span class="k">{{ 'status.cpu' | t }}</span>
          <span class="v">{{ s.cpu.toFixed(1) }} %</span>
        </p>
        <p class="tile">
          <span class="k">{{ 'status.memory' | t }}</span>
          <span class="v">{{ go(s.memory_bytes) }}</span>
        </p>
        <p class="tile">
          <span class="k">{{ 'status.disk' | t }}</span>
          <span class="v">{{ go(s.disk_bytes) }}</span>
        </p>
      }
    </div>
    <p role="alert" class="err">{{ status.error() }}</p>
  `,
})
export class StatusCard {
  protected readonly status = inject(Status);
  private readonly i18n = inject(I18n);
  protected readonly label = (state: string) => stateLabel(state, this.i18n.t);
  protected readonly go = (n: number) => fmtGo(n, this.i18n.t);
  protected readonly uptime = (ms: number) => fmtUptime(ms, this.i18n.t);
}
