# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auth.spec.ts >> Authentication & SaaS Routing Flow >> Registration page validates input and navigates properly
- Location: e2e\auth.spec.ts:45:7

# Error details

```
Error: expect(locator).toContainText(expected) failed

Locator: locator('h1')
Expected substring: "Create Your Workspace"
Received string:    "Create your Account"
Timeout: 10000ms

Call log:
  - Expect "toContainText" locator('h1') with timeout 10000ms
  - waiting for locator('h1')
    21 × locator resolved to <h1 class="text-2xl font-bold tracking-tight text-[var(--color-ink)]">Create your Account</h1>
       - unexpected value "Create your Account"

```

```yaml
- heading "Create your Account" [level=1]
```

# Test source

```ts
  1  | import { test, expect } from '@playwright/test';
  2  | 
  3  | test.describe('Authentication & SaaS Routing Flow', () => {
  4  |   test('Public Landing Page loads with SaaS Hero and CTAs', async ({ page }) => {
  5  |     await page.goto('/');
  6  |     
  7  |     // Check SaaS headline
  8  |     await expect(page.locator('h1')).toContainText('Turn raw transactions into an explainable financial review');
  9  |     
  10 |     // Check primary CTAs
  11 |     await expect(page.getByRole('link', { name: 'Start Free' }).first()).toBeVisible();
  12 |     await expect(page.getByRole('link', { name: 'Sign In' })).toBeVisible();
  13 |     
  14 |     // Check live financial intelligence snapshot section
  15 |     await expect(page.locator('text=Financial Intelligence Snapshot')).toBeVisible();
  16 |     await expect(page.locator('text=FinReview sample workspace')).toBeVisible();
  17 |   });
  18 | 
  19 |   test('Login failure displays graceful error message', async ({ page }) => {
  20 |     await page.goto('/login');
  21 |     
  22 |     await page.fill('#email', 'invalid.user@finreview.test');
  23 |     await page.fill('#password', 'WrongPassword123!');
  24 |     await page.click('button[type="submit"]');
  25 |     
  26 |     // Error notification must be displayed
  27 |     await expect(page.locator('[data-testid="auth-error-banner"]')).toBeVisible();
  28 |   });
  29 | 
  30 |   test('Successful login redirects user to /app workspace', async ({ page }) => {
  31 |     await page.goto('/login');
  32 |     
  33 |     await page.fill('#email', 'analyst@finreview.test');
  34 |     await page.fill('#password', 'Password123!');
  35 |     await page.click('button[type="submit"]');
  36 |     
  37 |     // Should redirect to /app
  38 |     await page.waitForURL('**/app');
  39 |     expect(page.url()).toContain('/app');
  40 |     
  41 |     // Header displays tenant name and role
  42 |     await expect(page.locator('text=NYC Restaurant Co.')).toBeVisible();
  43 |   });
  44 | 
  45 |   test('Registration page validates input and navigates properly', async ({ page }) => {
  46 |     await page.goto('/register');
  47 |     
> 48 |     await expect(page.locator('h1')).toContainText('Create Your Workspace');
     |                                      ^ Error: expect(locator).toContainText(expected) failed
  49 |     
  50 |     // Submitting empty form triggers validation
  51 |     await page.click('button[type="submit"]');
  52 |     await expect(page.locator('[data-testid="auth-error-banner"]')).toBeVisible();
  53 |   });
  54 | });
  55 | 
```