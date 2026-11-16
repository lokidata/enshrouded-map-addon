import { TestBed } from '@angular/core/testing';
import { ApiError } from '../../core/api';
import { I18n } from '../../core/i18n';
import {
  addCategory,
  Cats,
  csFailure,
  deleteCategory,
  filterItems,
  lines,
  previewText,
  renameCategory,
} from './chestsort.logic';

const cats: Cats = { Food: { words: ['a'], items: ['x'] }, Wood: { words: [], items: [] } };

describe('chestsort logic', () => {
  const t = (...a: Parameters<I18n['t']>) => {
    const i = TestBed.inject(I18n);
    i.set('fr');
    return i.t(...a);
  };
  afterEach(() => localStorage.clear());

  it('keeps every line but the empty ones, spaces included', () => {
    expect(lines('a\n\n b \n')).toEqual(['a', ' b ']);
    expect(lines('')).toEqual([]);
  });

  it('adds a trimmed new category, refusing empty and duplicate names (any case)', () => {
    expect(addCategory(cats, ' Ore ')).toEqual({
      cats: { ...cats, Ore: { words: [], items: [] } },
    });
    expect(addCategory(cats, '  ')).toEqual({ error: 'cs.name_required' });
    expect(addCategory(cats, 'food')).toEqual({ error: 'cs.name_taken' });
  });

  it('renames in place, keeping the order, and refuses a taken name', () => {
    const r = renameCategory(cats, 'Food', 'Meals') as { cats: Cats };
    expect(Object.keys(r.cats)).toEqual(['Meals', 'Wood']);
    expect(r.cats['Meals']).toBe(cats['Food']);
    expect(renameCategory(cats, 'Food', 'wood')).toEqual({
      error: 'cs.name_taken',
    });
    expect(renameCategory(cats, 'Food', 'Food')).toBeNull();
    expect(renameCategory(cats, 'Food', ' ')).toBeNull();
  });

  it('allows a case-only rename of the same category', () => {
    const r = renameCategory(cats, 'Food', 'FOOD') as { cats: Cats };
    expect(Object.keys(r.cats)).toEqual(['FOOD', 'Wood']);
  });

  it('deletes without touching the input', () => {
    expect(Object.keys(deleteCategory(cats, 'Food'))).toEqual(['Wood']);
    expect(Object.keys(cats)).toEqual(['Food', 'Wood']);
  });

  it('filters items by a case-insensitive substring', () => {
    expect(filterItems(['Iron Bar', 'wood'], ' IRON ')).toEqual(['Iron Bar']);
    expect(filterItems(['a', 'b'], '')).toEqual(['a', 'b']);
  });

  it('writes the preview', () => {
    expect(previewText({ errors: ['e'], warnings: ['w'], changed: true, diff: ['+x'] }, t)).toBe(
      'Erreurs :\n- e\n\nAvertissements :\n- w\n\nChangements :\n+x',
    );
    expect(previewText({ errors: [], warnings: [], changed: false, diff: [] }, t)).toBe(
      'Aucun changement.',
    );
  });

  it('names the copy to restore and the messages of a refusal', () => {
    expect(
      csFailure(new ApiError(502, 'rollback_failed', undefined, undefined, 'f.bak-1'), t),
    ).toContain('Copie à restaurer : f.bak-1.');
    expect(csFailure(new ApiError(422, 'invalid_content', undefined, ['m1', 'm2']), t)).toBe(
      'Le contenu est refusé.\n- m1\n- m2',
    );
    expect(csFailure(new ApiError(409, 'changed_elsewhere'), t)).toBe(
      'Le fichier a changé : rechargez.',
    );
    expect(csFailure(new ApiError(429, 'rate_limited', 5), t)).toBe(
      'Trop rapproché : réessayez dans 5 s.',
    );
  });

  it('speaks English too', () => {
    const i = TestBed.inject(I18n);
    i.set('en');
    expect(csFailure(new ApiError(409, 'changed_elsewhere'), i.t)).toBe(
      'The file changed: reload.',
    );
    expect(previewText({ errors: [], warnings: [], changed: false, diff: [] }, i.t)).toBe(
      'No changes.',
    );
  });
});
