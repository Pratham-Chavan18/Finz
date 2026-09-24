import { test, expect } from '@playwright/test';

test.describe('Transaction Ledger & Search Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.test');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Displays transaction ledger and filters rows via search input', async ({ page }) => {
    // Switch to Transactions tab
    await page.click('[data-testid="tab-transactions"]');

    // Stats bar should be visible
    await expect(page.locator('text=Total Inflows (Revenue)')).toBeVisible();
    await expect(page.locator('text=Total Outflows (Expenses)')).toBeVisible();

    // Search input should be present
    const searchInput = page.locator('[data-testid="transaction-search-input"]');
    await expect(searchInput).toBeVisible();

    // Type search query
    await searchInput.fill('Toast');
    await page.waitForTimeout(500); // debounce wait

    // Results should show Toast transactions
    await expect(page.locator('table')).toContainText('Toast');
  });
});
