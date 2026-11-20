import { TestBed } from '@angular/core/testing';
import { Api, ApiError } from './api';
import { Session } from './session';

function make(get: () => Promise<unknown>) {
  TestBed.configureTestingModule({ providers: [{ provide: Api, useValue: { get } }] });
  return TestBed.inject(Session);
}
const me = (level: 'read' | 'action' | null, chest: 'read' | 'action' | null = null) => ({
  username: 'u',
  is_admin: false,
  levels: { server: level, chestsort: chest },
  backup_filtered: true,
  chestsort: false,
});

describe('Session', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('only level action can act', async () => {
    const s = make(() => Promise.resolve(me('action')));
    await s.load();
    expect(s.canAct('server')).toBe(true);
    TestBed.resetTestingModule();
    const r = make(() => Promise.resolve(me('read')));
    await r.load();
    expect(r.canAct('server')).toBe(false);
  });

  it('no level means no access', async () => {
    const s = make(() => Promise.resolve(me(null)));
    await s.load();
    expect(s.hasAccess('server')).toBe(false);
    expect(s.hasAccess('chestsort')).toBe(false);
  });

  it('each add-on has its own level', async () => {
    const s = make(() => Promise.resolve(me(null, 'action')));
    await s.load();
    expect(s.hasAccess('server')).toBe(false);
    expect(s.canAct('server')).toBe(false);
    expect(s.hasAccess('chestsort')).toBe(true);
    expect(s.canAct('chestsort')).toBe(true);
  });

  it('a failed load keeps no user and says why', async () => {
    const s = make(() => Promise.reject(new ApiError(401)));
    await s.load();
    expect(s.me()).toBeNull();
    expect(s.error()).toBe("Connectez-vous d'abord sur le site.");
  });
});
