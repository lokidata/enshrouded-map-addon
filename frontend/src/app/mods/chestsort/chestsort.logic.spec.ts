import { TestBed } from '@angular/core/testing';
import { ApiError } from '../../core/api';
import { I18n } from '../../core/i18n';
import {
  addCategory,
  addItems,
  Cats,
  csFailure,
  deleteCategory,
  duplicates,
  filterItems,
  itemProblem,
  lines,
  moveItems,
  ownerOf,
  parseNames,
  prettyName,
  previewText,
  removeItem,
  renameCategory,
} from './chestsort.logic';

const cats: Cats = { Food: { words: ['a'], items: ['x'] }, Wood: { words: [], items: [] } };

describe('chestsort logic', () => {
  const t = (...a: Parameters<I18n['t']>) => {
    const i = TestBed.inject(I18n);
    i.setLang('fr');
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
    i.setLang('en');
    expect(csFailure(new ApiError(409, 'changed_elsewhere'), i.t)).toBe(
      'The file changed: reload.',
    );
    expect(previewText({ errors: [], warnings: [], changed: false, diff: [] }, i.t)).toBe(
      'No changes.',
    );
  });
});

describe('chestsort items: one item, one category', () => {
  const c = (): Cats => ({
    Food: { words: [], items: ['Apple', 'Bread'] },
    Metal: { words: [], items: ['Iron_Bar'] },
  });

  it('splits what is typed or pasted on lines, commas and semicolons, once per name', () => {
    expect(parseNames(' Iron_Bar,Tin_Bar;\n\n iron_bar \nCopper_Bar')).toEqual([
      'Iron_Bar',
      'Tin_Bar',
      'Copper_Bar',
    ]);
    expect(parseNames('  ')).toEqual([]);
  });

  it('refuses a name that is too long or has a control character', () => {
    expect(itemProblem('Iron_Bar')).toBeNull();
    expect(itemProblem('x'.repeat(201))).toBe('cs.item_invalid');
    expect(itemProblem('a\u0007b')).toBe('cs.item_invalid');
  });

  it('finds the owner of an item, ignoring the case, and who else holds it', () => {
    expect(ownerOf(c(), 'iron_bar')).toBe('Metal');
    expect(ownerOf(c(), 'iron_bar', 'Metal')).toBeNull();
    expect(ownerOf(c(), 'Nope')).toBeNull();
  });

  it('adds free items, and reports present, conflicting and invalid ones', () => {
    const r = addItems(c(), 'Food', ['Cheese', 'apple', 'Iron_Bar', 'x'.repeat(201)]);
    expect(r.cats['Food'].items).toEqual(['Apple', 'Bread', 'Cheese']);
    expect(r.added).toEqual(['Cheese']);
    expect(r.present).toEqual(['apple']);
    expect(r.conflicts).toEqual([{ item: 'Iron_Bar', from: 'Metal' }]);
    expect(r.invalid).toHaveLength(1);
    expect(r.cats['Metal'].items).toEqual(['Iron_Bar']); // a conflict moves nothing by itself
  });

  it('moves a conflicting item: out of the other category, into this one', () => {
    const r = addItems(c(), 'Food', ['iron_bar']);
    const next = moveItems(r.cats, 'Food', r.conflicts);
    expect(next['Metal'].items).toEqual([]);
    expect(next['Food'].items).toEqual(['Apple', 'Bread', 'iron_bar']);
    expect(duplicates(next)).toEqual([]);
  });

  it('removes one item from one category', () => {
    expect(removeItem(c(), 'Food', 'Apple')['Food'].items).toEqual(['Bread']);
    expect(c()['Food'].items).toEqual(['Apple', 'Bread']);
  });

  it('lists the items a loaded file already holds twice', () => {
    const d: Cats = { A: { words: [], items: ['X', 'Y'] }, B: { words: [], items: ['x'] } };
    expect(duplicates(d)).toEqual([{ item: 'X', cats: ['A', 'B'] }]);
    expect(duplicates(c())).toEqual([]);
  });
});

describe('prettyName', () => {
  it('makes an internal name readable', () => {
    expect(prettyName('Armor_lvl02_Tinko_Arms')).toBe('Armor lvl02 Tinko Arms');
    expect(prettyName('_Prop_Decoration_T5_Sideboard_Large')).toBe(
      'Prop Decoration T5 Sideboard Large',
    );
    expect(prettyName('Iron__Bar_')).toBe('Iron Bar');
  });
});
