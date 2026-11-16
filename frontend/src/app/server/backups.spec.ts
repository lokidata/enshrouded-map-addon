import { TestBed } from '@angular/core/testing';
import { NAVIGATE } from '../core/navigate';
import { ServerData } from '../core/server-data';
import { Backups } from './backups';
import { fakes, me } from '../../testing/fakes';

const done = {
  uuid: 'u-done',
  name: 'fini',
  bytes: 5 * 2 ** 20,
  created_at: '2026-01-01T00:00:00Z',
  completed_at: 'x',
  is_successful: true,
  is_locked: false,
};
const running = {
  ...done,
  uuid: 'u-run',
  name: 'encours',
  completed_at: null,
  is_successful: null,
};
const failed = { ...done, uuid: 'u-bad', name: 'raté', is_successful: false };

async function setup(opts: Parameters<typeof fakes>[0] = {}, rows = [done, running, failed]) {
  const f = fakes(opts);
  const navigate = vi.fn();
  TestBed.configureTestingModule({
    providers: [...f.providers, { provide: NAVIGATE, useValue: navigate }],
  });
  TestBed.inject(ServerData).backups.set(rows);
  const fx = TestBed.createComponent(Backups);
  fx.detectChanges();
  const el = fx.nativeElement as HTMLElement;
  const btn = (t: string) =>
    [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === t);
  return { f, fx, el, btn, navigate };
}

describe('Backups', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('labels unfinished and failed backups', async () => {
    const { el } = await setup();
    const rows = [...el.querySelectorAll('tbody tr')].map((r) => r.textContent);
    expect(rows[0]).not.toMatch(/en cours|échec/);
    expect(rows[1]).toContain('en cours');
    expect(rows[2]).toContain('échec');
  });

  it('a filtered backup is created without a dialog', async () => {
    const { f, fx, btn } = await setup();
    btn('Créer une sauvegarde')!.click();
    await fx.whenStable();
    expect(f.confirm.ask).not.toHaveBeenCalled();
    expect(f.api.post).toHaveBeenCalledWith('/backups', {});
  });

  it('an unfiltered backup warns first and sends confirm_full', async () => {
    const { f, fx, btn } = await setup({ me: me({ backup_filtered: false }) });
    btn('Créer une sauvegarde')!.click();
    await fx.whenStable();
    expect(f.confirm.ask).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Sauvegarder tout le serveur ?' }),
    );
    expect(f.api.post).toHaveBeenCalledWith('/backups', { confirm_full: true });
  });

  it('a declined warning sends nothing', async () => {
    const { f, fx, btn } = await setup({ me: me({ backup_filtered: false }), answer: false });
    btn('Créer une sauvegarde')!.click();
    await fx.whenStable();
    expect(f.api.post).not.toHaveBeenCalled();
  });

  it('only finished successful backups can be downloaded, and only by level action', async () => {
    const a = await setup();
    expect(a.el.querySelectorAll('button.dl').length).toBe(1);
    TestBed.resetTestingModule();
    const r = await setup({ me: me({ level: 'read' }) });
    expect(r.el.querySelectorAll('button.dl').length).toBe(0);
    expect(r.btn('Créer une sauvegarde')).toBeUndefined();
  });

  it('download navigates to the signed URL and never shows it', async () => {
    const { f, fx, el, navigate } = await setup();
    f.api.post.mockResolvedValue({ url: 'https://node.example/dl?token=SECRET' });
    (el.querySelector('button.dl') as HTMLButtonElement).click();
    await fx.whenStable();
    fx.detectChanges();
    expect(f.api.post).toHaveBeenCalledWith('/backups/u-done/download', {});
    expect(navigate).toHaveBeenCalledWith('https://node.example/dl?token=SECRET');
    expect(el.innerHTML).not.toContain('SECRET');
  });

  it('shows a list error and a not-ready download refusal', async () => {
    const { f, fx, el } = await setup();
    const { ApiError } = await import('../core/api');
    f.api.post.mockRejectedValue(new ApiError(409, 'backup_not_ready'));
    (el.querySelector('button.dl') as HTMLButtonElement).click();
    await fx.whenStable();
    fx.detectChanges();
    expect(el.textContent).toContain("Cette sauvegarde n'est pas terminée");
  });
});
