import { defineConfig, devices } from '@playwright/test';

const PORT = 4300;

// End-to-end tests drive the real Angular app in a browser. Supabase, Judge0
// and the OCR service are faked per test (see tests/e2e/support), because
// environment.ts points the app at the hosted Supabase project and a real run
// would write grades into production rows.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env['CI'],
  retries: process.env['CI'] ? 2 : 0,
  workers: process.env['CI'] ? 1 : undefined,
  reporter: process.env['CI'] ? 'html' : [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    // Submission cards show their capture time; a fixed zone keeps it stable.
    timezoneId: 'UTC',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: {
    // A dedicated port so the tests never attach to a dev server on 4200.
    command: `npx ng serve --port ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env['CI'],
    timeout: 180_000,
  },
});
