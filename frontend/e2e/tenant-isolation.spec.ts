import { test, expect } from '@playwright/test';

test.describe('Tenant Scoping & Multi-Tenancy Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.com');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Enforces authenticated tenant context in app header and settings', async ({ page }) => {
    // Current tenant badge
    await expect(page.locator('text=NYC Restaurant Co.').first()).toBeVisible();

    // Navigate to Team settings
    await page.click('a[href="/settings/team"]');
    await expect(page.locator('h1:has-text("Team & Permissions")')).toBeVisible();
    await expect(page.locator('text=Workspace Members')).toBeVisible();

    // Navigate back to /app and then to Chart of Accounts settings
    await page.click('a[href="/app"]');
    await page.click('a[href="/settings/chart-of-accounts"]');
    await expect(page.locator('h1:has-text("Chart of Accounts")')).toBeVisible();
  });
});
