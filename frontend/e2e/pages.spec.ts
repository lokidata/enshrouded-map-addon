import AxeBuilder from '@axe-core/playwright';
import { expect, Page, test } from '@playwright/test';

const backup = {
  uuid: 'u1',
  name: 'sauvegarde',
  bytes: 3 * 2 ** 20,
  created_at: '2026-01-01T00:00:00Z',
  completed_at: '2026-01-01T00:01:00Z',
  is_successful: true,
  is_locked: false,
};
const status = {
  name: 'S',
  state: 'running',
  cpu: 1.5,
  memory_bytes: 2 ** 30,
  disk_bytes: 2 ** 31,
  uptime_ms: 3_600_000,
};
const file = { categories: { Food: { words: ['a'], items: ['Apple'] } }, hash: 'h' };

interface Me {
  is_admin: boolean;
  level: 'read' | 'action' | null;
  chestsort: boolean;
}

// The screens are custom elements mounted by the site. Here a small host page stands in for it: the same
// wrapper ([data-addon]), the same attributes (lang, active), and a few of the site's tokens.
const TOKENS =
  ':root{--bad:#ff8a80;--gold:#cba867;--gold-dim:#8a7444;--accent:#eb9440;--muted:#a3adbd;--text:#e6e9ef;' +
  '--panel:#1a212d;--panel-deep:#141a23;--ink:#0d1117;--border:#303b4d;--ok:#7bc47f;' +
  '--mono:monospace;--display-sc:serif}body{margin:0;background:#0d1117;color:#e6e9ef;font-family:sans-serif}' +
  '[data-addon][hidden]{display:none}';

async function host(page: Page, tag: 'server' | 'chestsort', attrs = 'lang="fr"') {
  await page.route('**/host*', (route) =>
    route.fulfill({
      contentType: 'text/html',
      body:
        `<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>host</title>` +
        `<meta name="viewport" content="width=device-width, initial-scale=1">` +
        `<link rel="stylesheet" href="/addon/styles.css"><style>${TOKENS}</style>` +
        `<script type="module" src="/addon/main.js"></script></head><body>` +
        `<main><div data-addon><addon-${tag} ${attrs}></addon-${tag}></div></main></body></html>`,
    }),
  );
  await page.goto('/host');
}

async function mock(page: Page, me: Me = { is_admin: true, level: 'action', chestsort: true }) {
  await page.route('**/addon/api/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace('/addon/api', '');
    const body: Record<string, unknown> = {
      '/me': {
        username: 'root',
        backup_filtered: true,
        is_admin: me.is_admin,
        chestsort: me.chestsort,
        levels: { server: me.level, chestsort: me.level },
      },
      '/status': status,
      '/backups': [backup],
      '/journal': [
        {
          at: '2026-01-01T00:00:00Z',
          username: 'root',
          action: 'power',
          target: 'restart',
          result: 'ok',
        },
      ],
      '/chestsort': file,
      '/chestsort/backups': ['f.bak-1'],
    };
    return route.fulfill({ json: body[path] ?? {} });
  });
}

const errors = (page: Page) => {
  const list: string[] = [];
  page.on('console', (m) => m.type() === 'error' && list.push(m.text()));
  page.on('pageerror', (e) => list.push(e.message));
  return list;
};

async function axe(page: Page) {
  const r = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  expect(r.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`)).toEqual([]);
}

test('Server element: Pelican open, journal closed, no console error, AXE clean', async ({
  page,
}) => {
  const errs = errors(page);
  await mock(page);
  await host(page, 'server');
  const sections = page.locator('details.sec');
  await expect(sections).toHaveCount(2);
  await expect(page.getByRole('button', { name: 'Arrêter' })).toBeEnabled();
  expect(await sections.evaluateAll((d) => d.map((x) => (x as HTMLDetailsElement).open))).toEqual([
    true,
    false,
  ]);
  await axe(page);
  await page.locator('details.sec summary', { hasText: 'Journal' }).click();
  await axe(page);
  expect(errs).toEqual([]);
});

test('Chestsort element: text open, editor closed, AXE clean', async ({ page }) => {
  const errs = errors(page);
  await mock(page);
  await host(page, 'chestsort');
  expect(
    await page
      .locator('details.sec')
      .evaluateAll((d) => d.map((x) => (x as HTMLDetailsElement).open)),
  ).toEqual([true, false]);
  await expect(page.getByRole('heading', { name: 'storage' })).toBeVisible();
  await axe(page);
  await page.locator('details.sec summary', { hasText: 'Catégories de coffres' }).click();
  await expect(page.locator('#cs-words')).toHaveValue('a');
  await axe(page);
  expect(errs).toEqual([]);
});

test('level read: no action buttons', async ({ page }) => {
  await mock(page, { is_admin: false, level: 'read', chestsort: true });
  await host(page, 'server');
  await expect(page.getByRole('button', { name: 'Arrêter' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Télécharger' })).toHaveCount(0);
  await expect(page.locator('details.sec')).toHaveCount(2);
});

test('401 shows the French message on both elements', async ({ page }) => {
  await page.route('**/addon/api/**', (r) =>
    r.fulfill({ status: 401, json: { detail: 'unauthenticated' } }),
  );
  for (const tag of ['server', 'chestsort'] as const) {
    await host(page, tag);
    await expect(page.getByText("Connectez-vous d'abord sur le site.")).toBeVisible();
  }
});

test('phone width: no horizontal scroll', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mock(page);
  for (const tag of ['server', 'chestsort'] as const) {
    await host(page, tag);
    await expect(page.locator('details.sec').first()).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
  }
});

test('the stop dialog asks first', async ({ page }) => {
  await mock(page);
  await host(page, 'server');
  await page.getByRole('button', { name: 'Arrêter' }).click();
  const ok = page.getByRole('button', { name: 'Confirmer' });
  await expect(ok).toBeDisabled();
  await page.getByLabel("J'ai prévenu les joueurs").check();
  await expect(ok).toBeEnabled();
  await axe(page);
});

test('the lang attribute switches the text, German falls back to English', async ({ page }) => {
  const errs = errors(page);
  await mock(page);
  await host(page, 'server');
  const el = page.locator('addon-server');
  await el.evaluate((e) => e.setAttribute('lang', 'en'));
  await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeEnabled();
  await axe(page);
  await el.evaluate((e) => e.setAttribute('lang', 'de'));
  await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeEnabled();
  await el.evaluate((e) => e.setAttribute('lang', 'fr'));
  await expect(page.getByRole('button', { name: 'Arrêter' })).toBeEnabled();
  expect(errs).toEqual([]);
});

test('active="false" stops the status poll and keeps the element', async ({ page }) => {
  await mock(page);
  let polls = 0;
  await page.route('**/addon/api/status', (r) => {
    polls++;
    return r.fulfill({ json: status });
  });
  await host(page, 'server');
  await expect(page.getByRole('button', { name: 'Arrêter' })).toBeEnabled();
  await page.locator('addon-server').evaluate((e) => e.setAttribute('active', 'false'));
  const before = polls;
  await page.waitForTimeout(300);
  expect(polls).toBe(before);
  await page.locator('addon-server').evaluate((e) => e.setAttribute('active', 'true'));
  await expect.poll(() => polls).toBeGreaterThan(before); // a read at once on return
});
