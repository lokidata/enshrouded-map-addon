import { TestBed } from '@angular/core/testing';
import { ApiError } from './api';
import { I18n } from './i18n';
import { Key } from './lang.fr';
import { failure } from './reasons';

const err = (status: number, detail?: string, wait?: number) => new ApiError(status, detail, wait);
const codes = [
  'confirmation_required',
  'full_backup_confirmation_required',
  'invalid_request',
  'wrong_state',
  'pelican_rejected',
  'pelican_denied',
  'pelican_not_found',
  'pelican_unavailable',
  'pelican_timeout',
  'busy',
  'forbidden',
  'backup_not_ready',
];

describe('failure', () => {
  afterEach(() => localStorage.clear());

  it.each([
    ['confirmation_required', "Confirmez d'abord que les joueurs sont prévenus."],
    ['wrong_state', "Action impossible dans l'état actuel du serveur."],
    ['pelican_unavailable', 'Le panneau du serveur est injoignable.'],
    ['backup_not_ready', "Cette sauvegarde n'est pas terminée ou a échoué."],
  ])('%s (fr)', (detail, text) => {
    const i = TestBed.inject(I18n);
    i.setLang('fr');
    expect(failure(err(409, detail), i.t)).toBe(text);
  });

  it('every reason has a text in both languages', () => {
    const i = TestBed.inject(I18n);
    for (const lang of ['fr', 'en'] as const) {
      i.setLang(lang);
      for (const c of codes) expect(failure(err(409, c), i.t)).toBe(i.t(`err.${c}` as Key));
    }
  });

  it('429 says how long to wait, or says so vaguely', () => {
    const i = TestBed.inject(I18n);
    i.setLang('fr');
    expect(failure(err(429, 'rate_limited', 30), i.t)).toBe(
      'Trop rapproché : réessayez dans 30 s.',
    );
    expect(failure(err(429), i.t)).toBe('Trop rapproché : réessayez dans quelques secondes.');
    i.setLang('en');
    expect(failure(err(429, 'rate_limited', 30), i.t)).toBe('Too fast: try again in 30 s.');
  });

  it('falls back on the status', () => {
    const i = TestBed.inject(I18n);
    i.setLang('fr');
    expect(failure(err(401), i.t)).toBe("Connectez-vous d'abord sur le site.");
    expect(failure(err(503), i.t)).toBe('Le site est injoignable.');
    expect(failure(err(502), i.t)).toBe('Le panneau du serveur est injoignable.');
    expect(failure(err(500), i.t)).toBe('Erreur inattendue (500).');
    expect(failure(new TypeError('network'), i.t)).toBe('Erreur inattendue.');
    i.setLang('en');
    expect(failure(err(401), i.t)).toBe('Log in on the site first.');
  });
});
