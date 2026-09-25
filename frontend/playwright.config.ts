import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E configuration for FinReview SaaS.
 * Supports:
 * - Local development
 * - Headed & Headless modes
 * - Automatic screenshots on failure
 * - Retaining video on failure
 * - Tracing on failure
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60 * 1000,
  expect: {
    timeout: 15 * 1000,
  },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1, // sequential execution to preserve test database state
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: true,
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
