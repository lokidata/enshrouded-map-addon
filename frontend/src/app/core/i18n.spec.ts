import { TestBed } from '@angular/core/testing';
import { I18n } from './i18n';
import { de } from './lang.de';
import { en } from './lang.en';
import { fr } from './lang.fr';

const params = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('I18n', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => {
    vi.restoreAllMocks();
    TestBed.resetTestingModule();
  });

  it('English has exactly the French keys and the same {params}', () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(fr).sort());
    for (const [k, v] of Object.entries(fr))
      expect(params(en[k as keyof typeof en])).toEqual(params(v));
  });

  it('German has exactly the French keys and the same {params}', () => {
    expect(Object.keys(de).sort()).toEqual(Object.keys(fr).sort());
    for (const [k, v] of Object.entries(fr))
      expect(params(de[k as keyof typeof de])).toEqual(params(v));
  });

  it('starts in French; the site sets the language, and German is supported, others fall back to English', () => {
    const i = TestBed.inject(I18n);
    expect(i.lang()).toBe('fr');
    i.setLang('de');
    expect(i.lang()).toBe('de');
    i.setLang('fr');
    expect(i.lang()).toBe('fr');
    i.setLang('xx');
    expect(i.lang()).toBe('en');
  });

  it('keeps nothing in the browser storage', () => {
    TestBed.inject(I18n).setLang('en');
    expect(localStorage.getItem('addon-lang')).toBeNull();
  });

  it('translates, fills {params}, switches the locale', () => {
    const i = TestBed.inject(I18n);
    i.setLang('fr');
    expect(i.t('cs.words_n', { n: 3 })).toBe('3 mots');
    expect(i.locale()).toBe('fr-FR');
    i.setLang('en');
    expect(i.t('cs.words_n', { n: 3 })).toBe('3 words');
    expect(i.locale()).toBe('en-GB');
  });
});
