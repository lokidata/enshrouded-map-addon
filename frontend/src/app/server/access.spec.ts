import { TestBed } from '@angular/core/testing';
import { ApiError } from '../core/api';
import { ServerData } from '../core/server-data';
import { Access } from './access';
import { fakes } from '../../testing/fakes';

async function setup() {
  const f = fakes();
  TestBed.configureTestingModule({ providers: f.providers });
  TestBed.inject(ServerData).access.set([{ user_key: '2:t', username: 'alice', level: 'read' }]);
  const fx = TestBed.createComponent(Access);
  fx.detectChanges();
  const el = fx.nativeElement as HTMLElement;
  return { f, fx, el, sel: el.querySelector('select') as HTMLSelectElement };
}
const pick = (sel: HTMLSelectElement, v: string) => {
  sel.value = v;
  sel.dispatchEvent(new Event('change'));
};

describe('Access', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('lists users with their level', async () => {
    const { el, sel } = await setup();
    expect(el.textContent).toContain('alice');
    expect(sel.value).toBe('read');
  });

  it('a change is sent with the encoded key, and an empty level revokes', async () => {
    const { f, fx, sel } = await setup();
    pick(sel, 'action');
    await fx.whenStable();
    expect(f.api.put).toHaveBeenCalledWith('/access/2%3At', { level: 'action' });
    pick(sel, '');
    await fx.whenStable();
    expect(f.api.put).toHaveBeenLastCalledWith('/access/2%3At', { level: null });
  });

  it('a refusal puts the old level back and says why', async () => {
    const { f, fx, el, sel } = await setup();
    f.api.put.mockRejectedValue(new ApiError(403, 'forbidden'));
    pick(sel, 'action');
    await fx.whenStable();
    fx.detectChanges();
    expect(sel.value).toBe('read');
    expect(el.textContent).toContain('Action non autorisée.');
  });
});
