import { signal } from '@angular/core';
import { Api, ApiError } from '../app/core/api';
import { Confirm } from '../app/core/confirm';
import { Session, Me } from '../app/core/session';
import { Status } from '../app/core/status';

export const me = (over: Partial<Me> = {}): Me => ({
  username: 'u',
  is_admin: false,
  level: 'action',
  backup_filtered: true,
  chestsort: false,
  ...over,
});

/** Providers shared by the page specs: a fake API, a fake session and state, a confirm that answers. */
export function fakes(opts: { state?: string; me?: Me; answer?: boolean } = {}) {
  const api = {
    get: vi.fn().mockResolvedValue([]),
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
  };
  const who = signal(opts.me ?? me());
  const session = {
    me: who,
    canAct: () => who().level === 'action',
    hasAccess: () => who().level !== null,
  };
  const state = signal(opts.state ?? 'running');
  const status = {
    state,
    error: signal(''),
    info: signal(null),
    refresh: vi.fn().mockResolvedValue(undefined),
  };
  const confirm = { ask: vi.fn().mockResolvedValue(opts.answer ?? true), request: signal(null) };
  return {
    api,
    state,
    status,
    confirm,
    who,
    providers: [
      { provide: Api, useValue: api },
      { provide: Session, useValue: session },
      { provide: Status, useValue: status },
      { provide: Confirm, useValue: confirm },
    ],
  };
}
export { ApiError };
