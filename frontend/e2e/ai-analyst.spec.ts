import { test, expect } from '@playwright/test';

test.describe('Source-Grounded AI Analyst Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.test');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Displays AI Analyst chat and suggested prompt pills', async ({ page }) => {
    // Switch to AI Analyst tab
    await page.click('[data-testid="tab-chat"]');

    // Welcome message should be visible
    await expect(page.locator('text=FinReview AI Financial Analyst')).toBeVisible();

    // Suggested prompt pills should be clickable
    const promptPill = page.locator('text=What was our revenue in Jan 2026?');
    await expect(promptPill).toBeVisible();

    // Input box should be present
    const chatInput = page.locator('input[placeholder*="Ask a question"]');
    await expect(chatInput).toBeVisible();
  });
});
