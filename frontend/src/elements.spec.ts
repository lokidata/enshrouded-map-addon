const ME = {
  username: 'u',
  is_admin: false,
  levels: { server: null, chestsort: 'read' },
  backup_filtered: false,
  chestsort: false,
};

describe('custom elements', () => {
  beforeAll(async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => new Response(JSON.stringify(url.endsWith('/me') ? ME : []))),
    );
    await import('./elements');
  });
  afterAll(() => vi.unstubAllGlobals());

  it('defines both add-ons', async () => {
    for (const tag of ['addon-server', 'addon-chestsort']) {
      await customElements.whenDefined(tag);
      expect(customElements.get(tag)).toBeDefined();
    }
  });

  it('follows the lang attribute', async () => {
    await customElements.whenDefined('addon-chestsort');
    const el = document.createElement('addon-chestsort');
    el.setAttribute('lang', 'en');
    document.body.append(el);
    await new Promise((r) => setTimeout(r, 100));
    const en = el.textContent;
    el.setAttribute('lang', 'fr');
    await new Promise((r) => setTimeout(r, 100));
    expect(en).toBeTruthy();
    expect(el.textContent).not.toBe(en);
    el.remove();
  });
});
