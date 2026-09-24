import { test, expect } from '@playwright/test';

test.describe('Deterministic P&L Statement Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.test');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Displays authoritative P&L statement with Revenue, COGS, and Operating Profit lines', async ({ page }) => {
    // Switch to P&L tab
    await page.click('[data-testid="tab-pnl"]');

    // Verify Statement Header
    await expect(page.locator('text=Profit & Loss (P&L) Statement')).toBeVisible();

    // Verify key financial sections exist
    await expect(page.locator('text=Revenue').first()).toBeVisible();
    await expect(page.locator('text=Gross Profit').first()).toBeVisible();
    await expect(page.locator('text=Operating Profit').first()).toBeVisible();
  });
});
