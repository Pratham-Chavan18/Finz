import { test, expect } from '@playwright/test';

test.describe('FinReview Visual QA Capture', () => {
  test('Capture full visual suite of pages and components', async ({ page }) => {
    // 1. Landing Page
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/visual-01-landing.png', fullPage: true });

    // 2. Login Page
    await page.goto('/login');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/visual-02-login.png' });

    // 3. Login to /app
    await page.fill('#email', 'analyst@finreview.com');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    await page.waitForURL('**/app');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/visual-03-app-overview.png' });

    // 4. Ingest tab
    await page.click('[data-testid="tab-ingest"]');
    await page.waitForTimeout(300);
    await page.screenshot({ path: 'test-results/visual-04-ingest.png' });

    // 5. Transactions tab
    await page.click('[data-testid="tab-transactions"]');
    await page.waitForTimeout(400);
    await page.screenshot({ path: 'test-results/visual-05-transactions.png' });

    // 6. Review tab
    await page.click('[data-testid="tab-review"]');
    await page.waitForTimeout(400);
    await page.screenshot({ path: 'test-results/visual-06-review.png' });

    // 7. P&L Statement & Traceability Drawer
    await page.click('[data-testid="tab-pnl"]');
    await page.waitForTimeout(400);
    await page.screenshot({ path: 'test-results/visual-07-pnl.png' });

    // Open Traceability Drawer on EBITDA
    const traceBtn = page.locator('button:has-text("Trace ->")').first();
    if (await traceBtn.isVisible()) {
      await traceBtn.click();
      await page.waitForTimeout(400);
      await page.screenshot({ path: 'test-results/visual-08-traceability-drawer.png' });
      // Close drawer
      const closeBtn = page.locator('button[aria-label="Close drawer"]').or(page.locator('button:has-text("Close")')).first();
      if (await closeBtn.isVisible()) await closeBtn.click();
    }

    // 8. Variances tab
    await page.click('[data-testid="tab-variances"]');
    await page.waitForTimeout(400);
    await page.screenshot({ path: 'test-results/visual-09-variances.png' });

    // 9. AI Analyst tab
    await page.click('[data-testid="tab-chat"]');
    await page.waitForTimeout(400);
    await page.screenshot({ path: 'test-results/visual-10-ai-analyst.png' });

    // 10. Team Settings
    await page.click('a[href="/settings/team"]');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/visual-11-team-settings.png' });

    // 11. Chart of Accounts Settings
    await page.click('a[href="/app"]');
    await page.waitForLoadState('networkidle');
    await page.click('a[href="/settings/chart-of-accounts"]');
    await page.waitForLoadState('networkidle');
    await page.screenshot({ path: 'test-results/visual-12-chart-of-accounts.png' });
  });
});
