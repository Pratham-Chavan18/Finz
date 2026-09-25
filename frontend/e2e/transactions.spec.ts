import { test, expect } from '@playwright/test';

test.describe('Transaction Ledger & Search Flow', () => {
  test.beforeEach(async ({ page }) => {
    const { execSync } = require('child_process');
    try {
      execSync('python -c "import sys; sys.path.insert(0, \'../backend\'); from app.db.session import SessionLocal; from app.models.user import User; db=SessionLocal(); u=db.query(User).filter_by(email=\'analyst@finreview.com\').first(); (setattr(u, \'tenant_id\', 1), db.commit()) if u else None; db.close()"');
    } catch {}

    await page.goto('/login');
    await page.fill('#email', 'analyst@finreview.com');
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
