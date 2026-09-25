import { test, expect } from '@playwright/test';

test.describe('Onboarding Wizard Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Authenticate as analyst
    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.com');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
  });

  test('Renders 6-step onboarding wizard and progresses through company configuration', async ({ page }) => {
    await page.click('a[href="/onboarding"]');
    
    // Check Wizard Steps Header
    await expect(page.locator('text=Configure Your Company')).toBeVisible();
    await expect(page.getByText('Company', { exact: true }).first()).toBeVisible();
    await expect(page.locator('text=Connect Data')).toBeVisible();
    await expect(page.locator('text=Chart of Accounts')).toBeVisible();

    // Check company name input
    const companyInput = page.locator('input[placeholder*="NYC Restaurant Co."]');
    await expect(companyInput).toBeVisible();
    
    // Step forward to Connect Data
    await page.click('button:has-text("Continue")');
    
    // Should now be on Connect Data step
    await expect(page.locator('text=Connect Financial Data')).toBeVisible();
    await expect(page.locator('text=Load Bundled Restaurant Dataset (Recommended)')).toBeVisible();

    // Ingest sample data to advance wizard
    await page.click('button:has-text("Continue")');
    await expect(page.locator('h2:has-text("Chart of Accounts Mapping")')).toBeVisible({ timeout: 20000 });
  });

  test.afterAll(async () => {
    // Reset test user back to tenant 1 for deterministic multi-test consistency
    const { execSync } = require('child_process');
    try {
      execSync('python -c "import sys; sys.path.insert(0, \'../backend\'); from app.db.session import SessionLocal; from app.models.user import User; db=SessionLocal(); u=db.query(User).filter_by(email=\'analyst@finreview.com\').first(); (setattr(u, \'tenant_id\', 1), db.commit()) if u else None; db.close()"');
    } catch {}
  });
});
