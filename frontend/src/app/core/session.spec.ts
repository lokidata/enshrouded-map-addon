import { TestBed } from '@angular/core/testing';
import { Api, ApiError } from './api';
import { Session } from './session';

function make(get: () => Promise<unknown>) {
  TestBed.configureTestingModule({ providers: [{ provide: Api, useValue: { get } }] });
  return TestBed.inject(Session);
}
const me = (level: 'read' | 'action' | null) => ({
  username: 'u',
  is_admin: false,
  level,
  backup_filtered: true,
  chestsort: false,
});

describe('Session', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('only level action can act', async () => {
    const s = make(() => Promise.resolve(me('action')));
    await s.load();
    expect(s.canAct()).toBe(true);
    TestBed.resetTestingModule();
    const r = make(() => Promise.resolve(me('read')));
    await r.load();
    expect(r.canAct()).toBe(false);
  });

  it('no level means no access', async () => {
    const s = make(() => Promise.resolve(me(null)));
    await s.load();
    expect(s.hasAccess()).toBe(false);
  });

  it('a failed load keeps no user and says why', async () => {
    const s = make(() => Promise.reject(new ApiError(401)));
    await s.load();
    expect(s.me()).toBeNull();
    expect(s.error()).toBe("Connectez-vous d'abord sur le site.");
  });
});
