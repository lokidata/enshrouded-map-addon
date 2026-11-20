import { TestBed } from '@angular/core/testing';
import { fmtDate, fmtGo, fmtSize, fmtUptime } from './format';
import { I18n } from './i18n';

describe('format', () => {
  afterEach(() => localStorage.clear());

  it('sizes switch to the big unit at 1 GB, in the language of the page', () => {
    const i = TestBed.inject(I18n);
    i.setLang('fr');
    expect(fmtSize(5 * 2 ** 20, i.t)).toBe('5.0 Mo');
    expect(fmtSize(2 ** 30, i.t)).toBe('1.00 Go');
    expect(fmtGo(2 ** 31, i.t)).toBe('2.00 Go');
    i.setLang('en');
    expect(fmtSize(5 * 2 ** 20, i.t)).toBe('5.0 MB');
    expect(fmtGo(2 ** 31, i.t)).toBe('2.00 GB');
  });

  it('uptime in days, hours, minutes', () => {
    const i = TestBed.inject(I18n);
    i.setLang('fr');
    expect(fmtUptime((26 * 60 + 5) * 60000, i.t)).toBe('1 j 2 h 5 min');
    expect(fmtUptime(0, i.t)).toBe('0 j 0 h 0 min');
    i.setLang('en');
    expect(fmtUptime((26 * 60 + 5) * 60000, i.t)).toBe('1 d 2 h 5 min');
  });

  it('dates follow the locale', () => {
    expect(fmtDate('2026-01-31T12:00:00Z', 'en-GB')).toContain('31/01/2026');
    expect(fmtDate('2026-01-31T12:00:00Z', 'fr-FR')).toContain('31/01/2026');
  });
});
