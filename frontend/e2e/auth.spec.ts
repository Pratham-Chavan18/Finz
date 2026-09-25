import { test, expect } from '@playwright/test';

test.describe('Authentication & SaaS Routing Flow', () => {
  test('Public Landing Page loads with SaaS Hero and CTAs', async ({ page }) => {
    await page.goto('/');
    
    // Check SaaS headline
    await expect(page.locator('h1')).toContainText('Turn raw transactions into an explainable financial review');
    
    // Check primary CTAs
    await expect(page.getByRole('link', { name: 'Start Free' }).first()).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign In' })).toBeVisible();
    
    // Check live financial intelligence snapshot section
    await expect(page.locator('text=Financial Intelligence Snapshot')).toBeVisible();
    await expect(page.locator('text=FinReview sample workspace')).toBeVisible();
  });

  test('Login failure displays graceful error message', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('#email', 'invalid.user@finreview.com');
    await page.fill('#password', 'WrongPassword123!');
    await page.click('button[type="submit"]');
    
    // Error notification must be displayed
    await expect(page.locator('[data-testid="auth-error-banner"]')).toBeVisible();
  });

  test('Successful login redirects user to /app workspace', async ({ page }) => {
    await page.goto('/login');
    
    await page.fill('#email', 'analyst@finreview.com');
    await page.fill('#password', 'Password123!');
    await page.click('button[type="submit"]');
    
    // Should redirect to /app
    await page.waitForURL('**/app');
    expect(page.url()).toContain('/app');
    
    // Header displays tenant name and role
    await expect(page.locator('text=NYC Restaurant Co.').first()).toBeVisible();
  });

  test('Registration page validates input and navigates properly', async ({ page }) => {
    await page.goto('/register');
    
    await expect(page.locator('h1')).toContainText('Create your Account');
    
    // Submitting empty form triggers validation
    await page.click('button[type="submit"]');
    await expect(page.locator('[data-testid="auth-error-banner"]')).toBeVisible();
  });
});
