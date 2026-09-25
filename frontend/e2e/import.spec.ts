import { test, expect } from '@playwright/test';

test.describe('CSV Ingestion & Batch Processing Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.com');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Renders Ingestion Dropzone and triggers sample dataset loading', async ({ page }) => {
    // Switch to Ingest tab
    await page.click('[data-testid="tab-ingest"]');
    
    // Check dropzone container is visible
    await expect(page.locator('text=Drop bank transaction CSV file here')).toBeVisible();
    await expect(page.locator('[data-testid="load-sample-btn"]')).toBeVisible();

    // Trigger sample dataset load
    await page.click('[data-testid="load-sample-btn"]');

    // Ingest automatically completes and transitions to transactions ledger
    await expect(page.locator('text=Total Transactions').first()).toBeVisible({ timeout: 25000 });
    await expect(page.locator('text=181').first()).toBeVisible();
  });
});
