import { TestBed } from '@angular/core/testing';
import { ApiError } from '../../core/api';
import { fakes, me } from '../../../testing/fakes';
import { Chestsort } from './chestsort';

const file = {
  categories: {
    Food: { words: ['a b'], items: ['Apple', 'Bread'] },
    Wood: { words: [], items: [] },
  },
  hash: 'h1',
};

const chips = (el: HTMLElement) =>
  [...el.querySelectorAll('.cs-tile span:not(.cs-noicon)')].map((x) => x.textContent?.trim());

async function setup(opts: Parameters<typeof fakes>[0] = {}) {
  const f = fakes(opts);
  f.api.get.mockImplementation((p: string) =>
    Promise.resolve(
      p === '/chestsort' ? structuredClone(file) : p === '/chestsort/backups' ? ['f.bak-1'] : [],
    ),
  );
  f.api.post.mockResolvedValue({ errors: [], warnings: [], changed: true, diff: ['+x'] });
  TestBed.configureTestingModule({ providers: f.providers });
  const fx = TestBed.createComponent(Chestsort);
  await fx.whenStable();
  fx.detectChanges();
  const el = fx.nativeElement as HTMLElement;
  const q = <T extends Element>(s: string) => el.querySelector(s) as T;
  const btn = (t: string) =>
    [...el.querySelectorAll('button')].find((b) => b.textContent?.trim() === t) as
      HTMLButtonElement | undefined;
  const type = async (s: string, v: string) => {
    const e = q<HTMLTextAreaElement | HTMLInputElement>(s);
    e.value = v;
    e.dispatchEvent(new Event('input'));
    fx.detectChanges();
  };
  const choose = (name: string) =>
    (
      [...el.querySelectorAll('.cs-cat')].find((b) => b.textContent?.trim() === name) as HTMLElement
    ).click();
  const settle = async () => {
    await fx.whenStable();
    fx.detectChanges();
  };
  return { f, fx, el, q, btn, type, settle, choose };
}

describe('Chestsort', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('loads the file and shows the first category', async () => {
    const { q, el } = await setup();
    expect(q<HTMLTextAreaElement>('#cs-words').value).toBe('a b');
    expect(chips(el)).toEqual(['Apple', 'Bread']);
    expect(el.textContent).toContain('2 objets');
  });

  it('level read: read-only, no edit buttons', async () => {
    const { q, btn } = await setup({ me: me({ level: 'read' }) });
    expect(q<HTMLTextAreaElement>('#cs-words').readOnly).toBe(true);
    expect(btn('Enregistrer')).toBeUndefined();
    expect(btn('Ajouter')).toBeUndefined();
  });

  it('keeps lines as typed, dropping only empty ones', async () => {
    const { f, fx, q, btn, type, settle } = await setup();
    await type('#cs-words', ' a \n\nb');
    btn('Aperçu des changements')!.click();
    await settle();
    expect(f.api.post).toHaveBeenCalledWith('/chestsort/preview', {
      categories: expect.objectContaining({
        Food: { words: [' a ', 'b'], items: ['Apple', 'Bread'] },
      }),
    });
    expect(q<HTMLTextAreaElement>('#cs-words').value).toBe(' a \n\nb'); // the box is not rewritten while typing
    void fx;
  });

  it('a filter narrows the chips and shows a count', async () => {
    const { el, type } = await setup();
    await type('#cs-filter', 'app');
    expect(chips(el)).toEqual(['Apple']);
    expect(el.textContent).toContain('1 sur 2 objets');
  });

  it('adds items typed or pasted, one chip each, and says what was already there', async () => {
    const { el, btn, type, settle } = await setup();
    await type('#cs-add', 'Cheese, apple\nMilk');
    btn("Ajouter l'objet")!.click();
    await settle();
    expect(chips(el)).toEqual(['Apple', 'Bread', 'Cheese', 'Milk']);
    expect(el.textContent).toContain('Ajouté : Cheese, Milk.');
    expect(el.textContent).toContain('Déjà dans cette catégorie : apple.');
  });

  it('an item held by another category is not added until the user moves it', async () => {
    const { f, el, btn, type, settle, choose } = await setup();
    await type('#cs-name', 'x'); // keep the first category selected
    choose('Wood');
    await type('#cs-add', 'bread');
    btn("Ajouter l'objet")!.click();
    await settle();
    expect(chips(el)).toEqual([]);
    expect(el.textContent).toContain('« bread » est déjà dans « Food ».');
    btn('Déplacer ici')!.click();
    await settle();
    expect(chips(el)).toEqual(['bread']);
    btn('Aperçu des changements')!.click();
    await settle();
    expect(f.api.post).toHaveBeenCalledWith('/chestsort/preview', {
      categories: expect.objectContaining({
        Food: { words: ['a b'], items: ['Apple'] },
        Wood: { words: [], items: ['bread'] },
      }),
    });
  });

  it('leaving a conflict alone changes nothing', async () => {
    const { el, btn, type, settle, choose } = await setup();
    choose('Wood');
    await type('#cs-add', 'Apple');
    btn("Ajouter l'objet")!.click();
    await settle();
    btn('Laisser où ils sont')!.click();
    await settle();
    expect(chips(el)).toEqual([]);
    expect(el.textContent).not.toContain('Déplacer ici');
  });

  it('removes an item with its own button, and a read-only user has none', async () => {
    const { el, btn, settle } = await setup();
    (el.querySelector('[aria-label="Retirer Apple"]') as HTMLButtonElement).click();
    await settle();
    expect(chips(el)).toEqual(['Bread']);
    expect(btn('Enregistrer')!.disabled).toBe(true);
    TestBed.resetTestingModule();
    const ro = await setup({ me: me({ level: 'read' }) });
    expect(ro.el.querySelector('.cs-x')).toBeNull();
    expect(ro.el.querySelector('#cs-add')).toBeNull();
  });

  it('Save needs a preview without error; any edit disables it again', async () => {
    const { btn, type, settle } = await setup();
    expect(btn('Enregistrer')!.disabled).toBe(true);
    btn('Aperçu des changements')!.click();
    await settle();
    expect(btn('Enregistrer')!.disabled).toBe(false);
    await type('#cs-words', 'zz');
    expect(btn('Enregistrer')!.disabled).toBe(true);
  });

  it('a preview with errors does not enable Save', async () => {
    const { f, btn, settle } = await setup();
    f.api.post.mockResolvedValue({ errors: ['bad'], warnings: [], changed: true, diff: [] });
    btn('Aperçu des changements')!.click();
    await settle();
    expect(btn('Enregistrer')!.disabled).toBe(true);
  });

  it('a preview answer that arrives after a further edit is dropped', async () => {
    const { f, btn, type, settle } = await setup();
    let answer!: (v: unknown) => void;
    f.api.post.mockReturnValue(new Promise((r) => (answer = r)));
    btn('Aperçu des changements')!.click();
    await type('#cs-words', 'changed');
    answer({ errors: [], warnings: [], changed: true, diff: ['+old'] });
    await settle();
    expect(btn('Enregistrer')!.disabled).toBe(true);
  });

  it('saving asks the dialog, then sends confirm: true with the hash and reloads', async () => {
    const { f, el, btn, settle } = await setup();
    btn('Aperçu des changements')!.click();
    await settle();
    f.api.put.mockResolvedValue({ backup: 'f.bak-2', hash: 'h2' });
    btn('Enregistrer')!.click();
    await settle();
    expect(f.confirm.ask).toHaveBeenCalledWith(
      expect.objectContaining({ label: "J'ai relu les changements" }),
    );
    expect(f.api.put).toHaveBeenCalledWith('/chestsort', {
      categories: file.categories,
      base_hash: 'h1',
      confirm: true,
    });
    expect(el.textContent).toContain('Copie de secours : f.bak-2');
  });

  it('a declined save sends nothing', async () => {
    const { f, btn, settle } = await setup({ answer: false });
    btn('Aperçu des changements')!.click();
    await settle();
    btn('Enregistrer')!.click();
    await settle();
    expect(f.api.put).not.toHaveBeenCalled();
  });

  it('changed_elsewhere offers a reload; rollback_failed names the copy', async () => {
    const { f, el, btn, settle } = await setup();
    btn('Aperçu des changements')!.click();
    await settle();
    f.api.put.mockRejectedValue(new ApiError(409, 'changed_elsewhere'));
    btn('Enregistrer')!.click();
    await settle();
    expect(btn('Recharger le fichier')).toBeDefined();
    f.api.put.mockRejectedValue(
      new ApiError(502, 'rollback_failed', undefined, undefined, 'f.bak-9'),
    );
    btn('Enregistrer')!.click();
    await settle();
    expect(el.textContent).toContain('f.bak-9');
  });

  it('restores a listed copy after the dialog', async () => {
    const { f, btn, settle } = await setup();
    f.api.post.mockResolvedValue({ backup: 'f.bak-3', hash: 'h3' });
    btn('Restaurer')!.click();
    await settle();
    expect(f.confirm.ask).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Restaurer f.bak-1 ?' }),
    );
    expect(f.api.post).toHaveBeenCalledWith('/chestsort/restore', {
      name: 'f.bak-1',
      base_hash: 'h1',
      confirm: true,
    });
  });

  it('adds and renames a category, refusing a duplicate', async () => {
    const { el, q, btn, type, settle } = await setup();
    await type('#cs-name', 'Ore');
    btn('Ajouter')!.click();
    await settle();
    expect([...el.querySelectorAll('.cs-cat')].map((o) => o.textContent?.trim())).toEqual([
      'Food',
      'Wood',
      'Ore',
    ]);
    await type('#cs-name', 'wood');
    btn('Renommer')!.click();
    await settle();
    expect(el.textContent).toContain('Une catégorie porte déjà ce nom.');
    expect(q<HTMLInputElement>('#cs-name').value).toBe('wood');
  });

  it('deleting asks first', async () => {
    const { f, el, btn, settle } = await setup();
    btn('Supprimer')!.click();
    await settle();
    expect(f.confirm.ask).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Supprimer la catégorie « Food » ?' }),
    );
    expect([...el.querySelectorAll('.cs-cat')].map((o) => o.textContent?.trim())).toEqual(['Wood']);
  });
});

describe('Chestsort download', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('downloads the file the server builds from the edited categories, even read-only', async () => {
    const { f, btn, settle } = await setup({ me: me({ level: 'read' }) });
    f.api.post.mockResolvedValue({ name: 'chestsort_categories.json', text: '{"categories":{}}' });
    URL.createObjectURL = vi.fn().mockReturnValue('blob:x');
    URL.revokeObjectURL = vi.fn();
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);
    btn('Télécharger le fichier')!.click();
    await settle();
    expect(f.api.post).toHaveBeenCalledWith('/chestsort/export', { categories: file.categories });
    expect(click).toHaveBeenCalledOnce();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:x');
    click.mockRestore();
  });

  it('downloads nothing and shows the errors when the content is refused', async () => {
    const { f, el, btn, settle } = await setup();
    f.api.post.mockRejectedValue(
      new ApiError(422, 'invalid_content', undefined, ['« x » est dans deux catégories.']),
    );
    URL.createObjectURL = vi.fn();
    btn('Télécharger le fichier')!.click();
    await settle();
    expect(URL.createObjectURL).not.toHaveBeenCalled();
    expect(el.textContent).toContain('est dans deux catégories');
  });
});

describe('Chestsort catalogue', () => {
  afterEach(() => TestBed.resetTestingModule());
  const guid = '0002f740-86a7-4764-ad8e-06423588a054';
  const rows: [string, string, string, string, string][] = [
    ['Material_T2_Iron_Bar', 'Lingot de fer', 'Iron Bar', 'Eisenbarren', guid],
    ['Food_T1_Apple', 'Pomme', 'Apple', 'Apfel', ''],
  ];

  it('hides the paste box when the catalogue is there, and shows it without', async () => {
    const withCat = await setup({ catalog: rows });
    expect(withCat.el.querySelector('#cs-add')).toBeNull();
    TestBed.resetTestingModule();
    const without = await setup();
    expect(without.el.querySelector('#cs-add')).not.toBeNull();
  });

  it('filters the items of a category by their displayed name', async () => {
    const t = await setup({
      catalog: [
        ['Apple', 'Pomme', 'Apple', 'Apfel', ''],
        ['Bread', 'Pain', 'Bread', 'Brot', ''],
      ],
    });
    await t.type('#cs-filter', 'pom');
    expect(chips(t.el)).toEqual(['Pomme']);
    await t.type('#cs-filter', 'apple'); // the internal name is not searched
    expect(chips(t.el)).toEqual([]);
  });

  describe('picker popup', () => {
    beforeAll(() => {
      // jsdom has no modal dialogs
      const d = HTMLDialogElement.prototype;
      d.showModal ??= function (this: HTMLDialogElement) {
        this.setAttribute('open', '');
      };
      d.close ??= function (this: HTMLDialogElement) {
        this.removeAttribute('open');
      };
    });
    const open = async (cat: typeof rows) => {
      const t = await setup({ catalog: cat });
      [...t.el.querySelectorAll('button')]
        .find((b) => b.textContent?.includes('Parcourir'))
        ?.click();
      t.fx.detectChanges();
      return t;
    };
    const rowsOf = (el: HTMLElement) => [...el.querySelectorAll('.cs-pick-list li')];

    it('lists items by name with their picture and filters while typing', async () => {
      const { el, type } = await open(rows);
      expect(rowsOf(el).map((r) => r.querySelector('.cs-pick-name')?.textContent?.trim())).toEqual([
        'Lingot de fer',
        'Pomme',
      ]);
      expect(rowsOf(el)[0].querySelector('img')?.getAttribute('src')).toBe(`/items/${guid}.png`);
      await type('#pick-q', 'pom');
      expect(rowsOf(el)).toHaveLength(1);
      expect(el.querySelector('.cs-pick footer')?.textContent).toContain('1');
    });

    it('also finds items by the name of the category that holds them', async () => {
      const { el, type } = await open([['Apple', 'Pomme', 'Apple', 'Apple', ''], ...rows]);
      await type('#pick-q', 'food'); // Apple is in the category Food
      expect(rowsOf(el).map((r) => r.querySelector('.cs-pick-name')?.textContent)).toEqual([
        expect.stringContaining('Pomme'),
      ]);
    });

    it('speaks the language of the site', async () => {
      const { el, fx } = await open(rows);
      const { I18n } = await import('../../core/i18n');
      TestBed.inject(I18n).setLang('de');
      fx.detectChanges();
      expect(rowsOf(el)[0].querySelector('.cs-pick-name')?.textContent).toContain('Apfel');
    });

    it('adds an item, then shows it as already here', async () => {
      const { el, fx, f } = await open(rows);
      const add = rowsOf(el)[0].querySelector('button') as HTMLButtonElement;
      add.click();
      fx.detectChanges();
      expect(rowsOf(el)[0].querySelector('button')).toBeNull(); // no button: already here
      expect(rowsOf(el)[0].textContent).toContain('Déjà dans cette catégorie');
      void f;
    });

    it('moves an item held by another category', async () => {
      const { el, fx, choose } = await open([['Apple', 'Pomme', 'Apple', 'Apple', ''], ...rows]);
      // Food (selected) holds Apple only in the fixture as "Apple"; pick Bread from Wood: select Wood first
      choose('Wood');
      fx.detectChanges();
      const row = rowsOf(el).find((r) => r.textContent?.includes('Pomme'))!;
      expect(row.textContent).toContain('Food');
      (row.querySelector('button') as HTMLButtonElement).click();
      fx.detectChanges();
      expect(rowsOf(el).find((r) => r.textContent?.includes('Pomme'))?.textContent).toContain(
        'Déjà dans cette catégorie',
      );
    });
  });
});
