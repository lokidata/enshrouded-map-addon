import { defineConfig, devices } from '@playwright/test';
import { resolve } from 'node:path';

// The real add-on API process serves the built elements; a host page (see the spec) stands in for the site,
// and the API calls themselves are mocked in the spec: nothing talks to a panel or a site.
const db = `/tmp/addon-e2e-${process.pid}.db`;

export default defineConfig({
  testDir: './e2e',
  timeout: process.env['CI'] ? 60_000 : 30_000,
  use: { baseURL: 'http://127.0.0.1:4300' },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        locale: 'fr-FR',
        launchOptions: { args: ['--no-sandbox'] },
      },
    },
  ],
  webServer: {
    command: `rm -f ${db}* && uv run --project .. uvicorn addon.api:create_app --factory --port 4300`,
    url: 'http://127.0.0.1:4300/addon/main.js',
    env: {
      PELICAN_URL: 'https://panel.example.test',
      PELICAN_API_KEY: 'e2e',
      PELICAN_SERVER_ID: 'abcd1234',
      SITE_URL: 'http://site.example.test',
      DB_PATH: db,
      STATIC_DIR: resolve(__dirname, 'dist/browser'),
    },
    reuseExistingServer: false,
  },
});
