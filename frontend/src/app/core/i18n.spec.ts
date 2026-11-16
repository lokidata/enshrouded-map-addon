import { TestBed } from '@angular/core/testing';
import { I18n } from './i18n';
import { en } from './lang.en';
import { fr } from './lang.fr';

const params = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('I18n', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it('English has exactly the French keys and the same {params}', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
    for (const [k, v] of Object.entries(fr))
      expect(params(en[k as keyof typeof en])).toEqual(params(v));
  });

  it('follows the browser language the first time, English unless it is French', () => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('de-DE');
    expect(TestBed.inject(I18n).lang()).toBe('en');
    TestBed.resetTestingModule();
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('fr-CA');
    expect(TestBed.inject(I18n).lang()).toBe('fr');
  });

  it('remembers the choice, which wins over the browser', () => {
    TestBed.inject(I18n).set('en');
    TestBed.resetTestingModule();
    expect(TestBed.inject(I18n).lang()).toBe('en');
  });

  it('survives a storage that throws', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied');
    });
    const i = TestBed.inject(I18n);
    i.set('en');
    expect(i.t('nav.server')).toBe('Server');
  });

  it('translates, fills {params}, switches the page language and the locale', () => {
    const i = TestBed.inject(I18n);
    i.set('fr');
    expect(i.t('cs.words_n', { n: 3 })).toBe('3 mots');
    expect(i.locale()).toBe('fr-FR');
    i.set('en');
    expect(i.t('cs.words_n', { n: 3 })).toBe('3 words');
    expect(i.locale()).toBe('en-GB');
    TestBed.tick();
    expect(document.documentElement.lang).toBe('en');
  });
});
