import { signal } from '@angular/core';
import { Api, ApiError } from '../app/core/api';
import { Catalog, CatalogRow } from '../app/core/catalog';
import { Confirm } from '../app/core/confirm';
import { Session, Me, Level } from '../app/core/session';
import { Status } from '../app/core/status';

/** `level` is a shortcut for the same level on both add-ons. */
export const me = (over: Partial<Me> & { level?: Level } = {}): Me => {
  const { level = 'action', ...rest } = over;
  return {
    username: 'u',
    is_admin: false,
    levels: { server: level, chestsort: level },
    backup_filtered: true,
    chestsort: false,
    ...rest,
  };
};

/** Providers shared by the page specs: a fake API, a fake session and state, a confirm that answers. */
export function fakes(
  opts: { state?: string; me?: Me; answer?: boolean; catalog?: CatalogRow[] } = {},
) {
  const api = {
    get: vi.fn().mockResolvedValue([]),
    post: vi.fn().mockResolvedValue({}),
    put: vi.fn().mockResolvedValue({}),
  };
  const who = signal(opts.me ?? me());
  const session = {
    me: who,
    canAct: (a: 'server' | 'chestsort') => who().levels[a] === 'action',
    hasAccess: (a: 'server' | 'chestsort') => who().levels[a] !== null,
  };
  const state = signal(opts.state ?? 'running');
  const status = {
    state,
    error: signal(''),
    info: signal(null),
    refresh: vi.fn().mockResolvedValue(undefined),
  };
  const confirm = { ask: vi.fn().mockResolvedValue(opts.answer ?? true), request: signal(null) };
  const catalog = {
    rows: signal<CatalogRow[]>(opts.catalog ?? []),
    load: vi.fn().mockResolvedValue(undefined),
  };
  return {
    api,
    catalog,
    state,
    status,
    confirm,
    who,
    providers: [
      { provide: Api, useValue: api },
      { provide: Session, useValue: session },
      { provide: Status, useValue: status },
      { provide: Confirm, useValue: confirm },
      { provide: Catalog, useValue: catalog },
    ],
  };
}
export { ApiError };
