import { test, expect } from '@playwright/test';

test.describe('CSV Ingestion & Batch Processing Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.test');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Renders Ingestion Dropzone and triggers sample dataset loading', async ({ page }) => {
    // Switch to Ingest tab
    await page.click('[data-testid="tab-ingest"]');
    
    // Check dropzone container is visible
    await expect(page.locator('text=Drag & Drop Bank Statement CSV')).toBeVisible();
    await expect(page.locator('[data-testid="load-sample-btn"]')).toBeVisible();

    // Trigger sample dataset load
    await page.click('[data-testid="load-sample-btn"]');

    // Verify response / success banner or completed state
    await expect(page.locator('text=Successfully loaded sample dataset')).toBeVisible({ timeout: 15000 });
  });
});
