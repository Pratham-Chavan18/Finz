import { test, expect } from '@playwright/test';

test.describe('Onboarding Wizard Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate as analyst
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.test');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Renders 6-step onboarding wizard and progresses through company configuration', async ({ page }) => {
    await page.goto('/onboarding');
    
    // Check Wizard Steps Header
    await expect(page.locator('text=Configure Your Company')).toBeVisible();
    await expect(page.locator('text=Company')).toBeVisible();
    await expect(page.locator('text=Connect Data')).toBeVisible();
    await expect(page.locator('text=Chart of Accounts')).toBeVisible();

    // Check company name input
    const companyInput = page.locator('input[placeholder="e.g. Acme Hospitality LLC"]');
    await expect(companyInput).toBeVisible();
    
    // Step forward
    await page.click('button:has-text("Continue")');
    
    // Should now be on Connect Data step
    await expect(page.locator('text=Connect Financial Data')).toBeVisible();
    await expect(page.locator('text=Load Bundled Restaurant Dataset (Recommended)')).toBeVisible();
  });
});
