import { Component, inject } from '@angular/core';
import { fmtDate } from '../core/format';
import { I18n, T } from '../core/i18n';
import { ServerData } from '../core/server-data';

@Component({
  imports: [T],
  selector: 'app-journal',
  template: `
    <p role="alert" class="err">{{ data.journalError() }}</p>
    <div class="scroll" tabindex="0" role="region" [attr.aria-label]="'sec.journal' | t">
      <table>
        <thead>
          <tr>
            <th>{{ 'journal.date' | t }}</th>
            <th>{{ 'journal.user' | t }}</th>
            <th>{{ 'journal.action' | t }}</th>
            <th>{{ 'journal.target' | t }}</th>
            <th>{{ 'journal.result' | t }}</th>
          </tr>
        </thead>
        <tbody>
          @for (r of data.journal(); track $index) {
            <tr>
              <td>{{ date(r.at) }}</td>
              <td>{{ r.username }}</td>
              <td>{{ r.action }}</td>
              <td>{{ r.target }}</td>
              <td>{{ r.result }}</td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class Journal {
  protected readonly data = inject(ServerData);
  private readonly i18n = inject(I18n);
  protected readonly date = (iso: string) => fmtDate(iso, this.i18n.locale());
}
