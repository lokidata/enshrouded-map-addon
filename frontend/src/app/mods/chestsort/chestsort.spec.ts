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
  const settle = async () => {
    await fx.whenStable();
    fx.detectChanges();
  };
  return { f, fx, el, q, btn, type, settle };
}

describe('Chestsort', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('loads the file and shows the first category', async () => {
    const { q, el } = await setup();
    expect(q<HTMLTextAreaElement>('#cs-words').value).toBe('a b');
    expect(q<HTMLTextAreaElement>('#cs-items').value).toBe('Apple\nBread');
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

  it('a filter makes the items read-only and shows a count', async () => {
    const { el, q, type } = await setup();
    await type('#cs-filter', 'app');
    expect(q<HTMLTextAreaElement>('#cs-items').value).toBe('Apple');
    expect(q<HTMLTextAreaElement>('#cs-items').readOnly).toBe(true);
    expect(el.textContent).toContain('1 sur 2 objets');
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
    expect([...el.querySelectorAll('#cs-list option')].map((o) => o.textContent)).toEqual([
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
    expect([...el.querySelectorAll('#cs-list option')].map((o) => o.textContent)).toEqual(['Wood']);
  });
});
