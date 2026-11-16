import { Component, inject } from '@angular/core';
import { fmtGo, fmtUptime } from '../core/format';
import { I18n, T } from '../core/i18n';
import { Status, stateLabel } from '../core/status';

@Component({
  imports: [T],
  selector: 'app-status-card',
  template: `
    <dl>
      <dt>{{ 'status.state' | t }}</dt>
      <dd>{{ label(status.state()) }}</dd>
      @if (status.info(); as s) {
        <dt>{{ 'status.cpu' | t }}</dt>
        <dd>{{ s.cpu.toFixed(1) }} %</dd>
        <dt>{{ 'status.memory' | t }}</dt>
        <dd>{{ go(s.memory_bytes) }}</dd>
        <dt>{{ 'status.disk' | t }}</dt>
        <dd>{{ go(s.disk_bytes) }}</dd>
        <dt>{{ 'status.uptime' | t }}</dt>
        <dd>{{ uptime(s.uptime_ms) }}</dd>
      }
    </dl>
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
