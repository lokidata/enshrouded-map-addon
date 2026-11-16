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

async function mock(page: Page, me: Me = { is_admin: true, level: 'action', chestsort: true }) {
  await page.route('**/addon/api/**', (route) => {
    const path = new URL(route.request().url()).pathname.replace('/addon/api', '');
    const body: Record<string, unknown> = {
      '/me': { username: 'root', backup_filtered: true, ...me },
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
      '/access': [{ user_key: '2:t', username: 'alice', level: 'read' }],
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

test.beforeEach(async ({ page }) => {
  // once per tab: a reload must keep what the page stored
  await page.addInitScript(() => {
    if (sessionStorage.getItem('e2e-clean')) return;
    sessionStorage.setItem('e2e-clean', '1');
    localStorage.clear();
  });
});

test('Serveur page: Pelican open, journal and access closed, no console error, AXE clean', async ({
  page,
}) => {
  const errs = errors(page);
  await mock(page);
  await page.goto('/addon/');
  const sections = page.locator('details.sec');
  await expect(sections).toHaveCount(3);
  await expect(page.getByRole('button', { name: 'Arrêter' })).toBeEnabled();
  expect(await sections.evaluateAll((d) => d.map((x) => (x as HTMLDetailsElement).open))).toEqual([
    true,
    false,
    false,
  ]);
  await axe(page);
  await page.locator('details.sec summary', { hasText: 'Journal' }).click();
  await page.locator('details.sec summary', { hasText: 'Accès' }).click();
  await axe(page);
  expect(errs).toEqual([]);
});

test('Mods page: text open, editor closed, deep link works, AXE clean', async ({ page }) => {
  const errs = errors(page);
  await mock(page);
  await page.goto('/addon/mods');
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

test('level read: no action buttons, no editor buttons', async ({ page }) => {
  await mock(page, { is_admin: false, level: 'read', chestsort: true });
  await page.goto('/addon/');
  await expect(page.getByRole('button', { name: 'Arrêter' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Télécharger' })).toHaveCount(0);
  await expect(page.locator('details.sec')).toHaveCount(2); // no access section
});

test('401 shows the French message on both pages', async ({ page }) => {
  await page.route('**/addon/api/**', (r) =>
    r.fulfill({ status: 401, json: { detail: 'unauthenticated' } }),
  );
  for (const url of ['/addon/', '/addon/mods']) {
    await page.goto(url);
    await expect(page.getByText("Connectez-vous d'abord sur le site.")).toBeVisible();
  }
});

test('phone width: no horizontal scroll', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await mock(page);
  for (const url of ['/addon/', '/addon/mods']) {
    await page.goto(url);
    await expect(page.locator('details.sec').first()).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true);
  }
});

test('the stop dialog asks first', async ({ page }) => {
  await mock(page);
  await page.goto('/addon/');
  await page.getByRole('button', { name: 'Arrêter' }).click();
  const ok = page.getByRole('button', { name: 'Confirmer' });
  await expect(ok).toBeDisabled();
  await page.getByLabel("J'ai prévenu les joueurs").check();
  await expect(ok).toBeEnabled();
  await axe(page);
});

test('dark and light schemes both render the plates', async ({ page }) => {
  await mock(page);
  for (const scheme of ['dark', 'light'] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto('/addon/');
    await expect(page.locator('details.sec').first()).toBeVisible();
  }
});

test('English version: switch, page language, remembered after a reload, AXE clean', async ({
  page,
}) => {
  const errs = errors(page);
  await mock(page);
  await page.goto('/addon/');
  await page.getByRole('button', { name: 'EN' }).click();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeEnabled();
  await expect(page.getByRole('link', { name: 'Server', exact: true })).toBeVisible();
  await axe(page);
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await page.getByRole('link', { name: 'Mods' }).click();
  await expect(page.getByText('not required')).toBeVisible();
  await axe(page);
  await page.getByRole('button', { name: 'FR' }).click();
  await expect(page.getByText('pas obligatoire')).toBeVisible();
  expect(errs).toEqual([]);
});

test('the first visit follows the browser language', async ({ browser }) => {
  const ctx = await browser.newContext({ locale: 'de-DE' });
  const page = await ctx.newPage();
  await mock(page);
  await page.goto('/addon/');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await ctx.close();
  const fr = await browser.newContext({ locale: 'fr-FR' });
  const p2 = await fr.newPage();
  await mock(p2);
  await p2.goto('/addon/');
  await expect(p2.locator('html')).toHaveAttribute('lang', 'fr');
  await fr.close();
});
