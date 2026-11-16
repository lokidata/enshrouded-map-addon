import { Component, inject, signal } from '@angular/core';
import { Api } from '../core/api';
import { I18n, T } from '../core/i18n';
import { failure } from '../core/reasons';
import { AccessRow, ServerData } from '../core/server-data';

/** Administrator only: who may read and who may act. */
@Component({
  imports: [T],
  selector: 'app-access',
  template: `
    <p role="alert" class="err">{{ error() || data.accessError() }}</p>
    <div class="scroll" tabindex="0" role="region" [attr.aria-label]="'sec.access' | t">
      <table>
        <thead>
          <tr>
            <th>Utilisateur</th>
            <th>Niveau</th>
          </tr>
        </thead>
        <tbody>
          @for (u of data.access(); track u.user_key) {
            <tr>
              <td>
                <label [for]="id(u)">{{ u.username }}</label>
              </td>
              <td>
                <select [id]="id(u)" [value]="u.level ?? ''" (change)="set(u, $event)">
                  <option value="">{{ 'access.none' | t }}</option>
                  <option value="read">{{ 'access.read' | t }}</option>
                  <option value="action">{{ 'access.action' | t }}</option>
                </select>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
})
export class Access {
  private readonly api = inject(Api);
  private readonly i18n = inject(I18n);
  protected readonly data = inject(ServerData);
  protected readonly error = signal('');

  protected id(u: AccessRow): string {
    return 'lvl-' + u.user_key.replace(/\W/g, '_');
  }

  protected async set(u: AccessRow, e: Event): Promise<void> {
    const sel = e.target as HTMLSelectElement;
    const level = (sel.value || null) as AccessRow['level'];
    try {
      await this.api.put('/access/' + encodeURIComponent(u.user_key), { level });
      this.error.set('');
      u.level = level;
    } catch (err) {
      this.error.set(failure(err, this.i18n.t));
      sel.value = u.level ?? '';
    }
  }
}
