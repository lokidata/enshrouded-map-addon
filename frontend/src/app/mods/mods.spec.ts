import { TestBed } from '@angular/core/testing';
import { ApiBase } from '../core/api';
import { I18n } from '../core/i18n';
import { Session } from '../core/session';
import { fakes, me } from '../../testing/fakes';
import { Mods } from './mods';

function setup(opts: Parameters<typeof fakes>[0], session: Record<string, unknown> = {}) {
  const f = fakes(opts);
  f.api.get.mockImplementation((p: string) =>
    Promise.resolve(
      p === '/chestsort' ? { categories: { Food: { words: ['a'], items: ['x'] } }, hash: 'h' } : [],
    ),
  );
  const base = f.providers.find((p) => p.provide === Session)!.useValue as Record<string, unknown>;
  TestBed.configureTestingModule({
    providers: [
      ...f.providers.filter((p) => p.provide !== Session),
      { provide: Session, useValue: { ...base, loaded: () => true, error: () => '', ...session } },
    ],
  });
  const fx = TestBed.createComponent(Mods);
  fx.detectChanges();
  return { fx, el: fx.nativeElement as HTMLElement };
}
const secs = (el: HTMLElement) => [...el.querySelectorAll('details')];

describe('Mods', () => {
  afterEach(() => {
    TestBed.resetTestingModule();
    localStorage.clear();
  });

  it('takes the base attribute, also after the first render, and ignores a bad one', () => {
    const { fx } = setup({ me: me() });
    fx.componentRef.setInput('base', '/addon/main/');
    fx.detectChanges();
    expect(TestBed.inject(ApiBase).base()).toBe('/addon/main/');
    fx.componentRef.setInput('base', '//evil.test/');
    fx.detectChanges();
    expect(TestBed.inject(ApiBase).base()).toBe('/addon/main/');
  });

  it('opens the mods text and closes the editor', () => {
    const { el } = setup({ me: me({ chestsort: true }) });
    expect(secs(el).map((d) => d.open)).toEqual([true, false]);
  });

  it('describes chestsort and storage, and no other mod', () => {
    const { el } = setup({ me: me() });
    const text = el.textContent ?? '';
    expect(text).toContain('chestsort');
    expect(text).toContain('storage');
    for (const other of ['assistants', 'meter', 'gemforge'])
      expect(text.toLowerCase()).not.toContain(other);
  });

  it('explains the client plugin: optional, install, slot locks, English search', () => {
    const { el } = setup({ me: me() });
    const text = el.textContent ?? '';
    for (const part of [
      'pas obligatoire',
      'dinput8.dll',
      'Verrouiller des emplacements',
      'version validée, v0.8.0',
      'en anglais',
    ]) {
      expect(text).toContain(part);
    }
    const hrefs = [...el.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).toContain(
      'https://github.com/bjck/shroudlink/releases/download/v0.8.0/shroudlink-client.zip',
    );
    expect(hrefs).toContain('https://github.com/bjck/shroudlink/releases');
    for (const a of el.querySelectorAll('a')) expect(a.getAttribute('rel')).toContain('noopener');
  });

  it('hides the editor when the server has no chestsort file', () => {
    const { el } = setup({ me: me({ chestsort: false }) });
    expect(secs(el).length).toBe(1);
    expect(el.querySelector('app-chestsort')).toBeNull();
  });

  it('says so without access, and shows an error once', () => {
    expect(setup({ me: me({ level: null }) }, { hasAccess: () => false }).el.textContent).toContain(
      'Accès non accordé',
    );
    TestBed.resetTestingModule();
    expect(
      setup({ me: me() }, { error: () => "Connectez-vous d'abord sur le site." }).el.textContent,
    ).toContain('Connectez-vous');
  });

  it('has the same explanation in English', () => {
    const { fx, el } = setup({ me: me({ chestsort: true }) });
    TestBed.inject(I18n).setLang('en');
    fx.detectChanges();
    const text = el.textContent ?? '';
    for (const part of [
      'not required',
      'Searches are in English',
      'Lock slots',
      'dinput8.dll',
      'Server mods',
    ]) {
      expect(text).toContain(part);
    }
    expect(text).not.toContain('pas obligatoire');
    expect(text.toLowerCase()).not.toContain('assistants');
    const hrefs = [...el.querySelectorAll('a')].map((a) => a.getAttribute('href'));
    expect(hrefs).toContain(
      'https://github.com/bjck/shroudlink/releases/download/v0.8.0/shroudlink-client.zip',
    );
  });
});
