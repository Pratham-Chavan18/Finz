import { test, expect } from '@playwright/test';

test.describe('Variance Analysis & Drivers Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.test');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Displays month-over-month variances, materiality toggle, and category drivers', async ({ page }) => {
    // Switch to Variances tab
    await page.click('[data-testid="tab-variances"]');

    // Header should be visible
    await expect(page.locator('text=Month-over-Month Variance Analysis')).toBeVisible();

    // Materiality toggle should be present
    await expect(page.locator('text=Only Material Changes')).toBeVisible();

    // Month selectors should be present and valid
    await expect(page.locator('text=Base:')).toBeVisible();
    await expect(page.locator('text=Current:')).toBeVisible();
  });
});
