import { TestBed } from '@angular/core/testing';
import { ApiError } from '../core/api';
import { Power } from './power';
import { fakes } from '../../testing/fakes';

function setup(state: string, answer = true) {
  const f = fakes({ state, answer });
  TestBed.configureTestingModule({ providers: f.providers });
  const fx = TestBed.createComponent(Power);
  fx.detectChanges();
  const el = fx.nativeElement as HTMLElement;
  const btn = (t: string) =>
    [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === t)!;
  return { f, fx, el, btn };
}
const enabled = (btn: (t: string) => HTMLButtonElement) =>
  ['Démarrer', 'Arrêter', 'Redémarrer'].filter((t) => !btn(t).disabled);

describe('Power', () => {
  afterEach(() => TestBed.resetTestingModule());

  it.each([
    ['offline', ['Démarrer']],
    ['running', ['Arrêter', 'Redémarrer']],
    ['unknown', []],
    ['starting', []],
  ])('state %s enables %j', (state, expected) => {
    expect(enabled(setup(state).btn)).toEqual(expected);
  });

  it('stop asks first, then sends confirm: true', async () => {
    const { f, fx, btn } = setup('running');
    btn('Arrêter').click();
    await fx.whenStable();
    expect(f.confirm.ask).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Arrêter le serveur ?', label: "J'ai prévenu les joueurs" }),
    );
    expect(f.api.post).toHaveBeenCalledWith('/power', { signal: 'stop', confirm: true });
  });

  it('a declined confirmation sends nothing', async () => {
    const { f, fx, btn } = setup('running', false);
    btn('Redémarrer').click();
    await fx.whenStable();
    expect(f.api.post).not.toHaveBeenCalled();
  });

  it('start sends no confirmation and asks nothing', async () => {
    const { f, fx, btn } = setup('offline');
    btn('Démarrer').click();
    await fx.whenStable();
    expect(f.confirm.ask).not.toHaveBeenCalled();
    expect(f.api.post).toHaveBeenCalledWith('/power', { signal: 'start' });
  });

  it('says it was asked, then reloads state, backups and journal', async () => {
    const { f, fx, el, btn } = setup('offline');
    btn('Démarrer').click();
    await fx.whenStable();
    fx.detectChanges();
    expect(el.textContent).toContain('Démarrage demandé.');
    expect(f.status.refresh).toHaveBeenCalled();
    expect(f.api.get).toHaveBeenCalledWith('/backups');
    expect(f.api.get).toHaveBeenCalledWith('/journal');
  });

  it('shows the wait of a 429', async () => {
    const { f, fx, el, btn } = setup('offline');
    f.api.post.mockRejectedValue(new ApiError(429, 'rate_limited', 30));
    btn('Démarrer').click();
    await fx.whenStable();
    fx.detectChanges();
    expect(el.textContent).toContain('réessayez dans 30 s');
  });
});
