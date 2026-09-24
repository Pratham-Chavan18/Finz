import { test, expect } from '@playwright/test';

test.describe('Human Review Queue & Audit Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.test');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Displays Review Queue and Audit Trail ledger', async ({ page }) => {
    // Switch to Review Queue tab
    await page.click('[data-testid="tab-review"]');

    // Check header
    await expect(page.locator('h3:has-text("Human Review Queue")')).toBeVisible();

    // Check Audit Trail section
    await expect(page.locator('text=Audit Trail')).toBeVisible();

    // Either flagged items exist or all items are verified
    const hasItems = await page.locator('text=Confirm').count() > 0;
    const allVerified = await page.locator('text=All Transactions Verified').count() > 0;
    expect(hasItems || allVerified).toBeTruthy();
  });
});
