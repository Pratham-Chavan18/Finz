# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: auth.spec.ts >> Authentication & SaaS Routing Flow >> Successful login redirects user to /app workspace
- Location: e2e\auth.spec.ts:30:7

# Error details

```
Test timeout of 30000ms exceeded.
```

```
Error: page.waitForURL: Test timeout of 30000ms exceeded.
=========================== logs ===========================
waiting for navigation to "**/app" until "load"
============================================================
```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [active]:
    - generic [ref=e4]:
      - generic [ref=e5]:
        - navigation [ref=e7]:
          - button [disabled] [ref=e8]:
            - img "previous" [ref=e9]
          - generic [ref=e11]:
            - generic [ref=e12]: 1/
            - generic [ref=e13]: "1"
          - button [disabled] [ref=e14]:
            - img "next" [ref=e15]
        - generic [ref=e18]:
          - generic "Latest available version is detected (16.3.6)." [ref=e21]: Next.js 16.3.6
          - generic [ref=e22]: Turbopack
      - dialog "Runtime Error" [ref=e24]:
        - generic [ref=e27]:
          - generic [ref=e29]:
            - generic [ref=e30]:
              - generic [ref=e31]: Runtime Error
              - generic [ref=e33]:
                - button "Copy Error Info" [ref=e34] [cursor=pointer]
                - button "No related documentation found" [disabled] [ref=e37]
                - button "Attach Node.js inspector" [ref=e40] [cursor=pointer]
            - generic [ref=e49]: "Objects are not valid as a React child (found: object with keys {type, loc, msg, input, ctx}). If you meant to render a collection of children, use an array instead."
          - generic [ref=e53]:
            - paragraph [ref=e54]:
              - text: Call Stack
              - generic [ref=e55]: "16"
            - button "Show 16 ignore-listed frame(s)" [ref=e56] [cursor=pointer]
    - generic [ref=e63] [cursor=pointer]:
      - button "Open Next.js Dev Tools" [ref=e64]
      - generic [ref=e68]:
        - button "Open issues overlay" [ref=e69]:
          - generic [ref=e70]:
            - generic [aria-hidden] [ref=e71]: "0"
            - generic [ref=e72]: "1"
          - generic [ref=e73]: Issue
        - button "Collapse issues badge" [ref=e74]
  - generic [ref=e78]:
    - heading "This page couldn’t load" [level=1] [ref=e81]
    - paragraph [ref=e82]: Reload to try again, or go back.
    - generic [ref=e83]:
      - button "Reload" [ref=e85] [cursor=pointer]
      - button "Back" [ref=e86] [cursor=pointer]
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
> 38 |     await page.waitForURL('**/app');
     |                ^ Error: page.waitForURL: Test timeout of 30000ms exceeded.
  39 |     expect(page.url()).toContain('/app');
  40 |     
  41 |     // Header displays tenant name and role
  42 |     await expect(page.locator('text=NYC Restaurant Co.')).toBeVisible();
  43 |   });
  44 | 
  45 |   test('Registration page validates input and navigates properly', async ({ page }) => {
  46 |     await page.goto('/register');
  47 |     
  48 |     await expect(page.locator('h1')).toContainText('Create Your Workspace');
  49 |     
  50 |     // Submitting empty form triggers validation
  51 |     await page.click('button[type="submit"]');
  52 |     await expect(page.locator('[data-testid="auth-error-banner"]')).toBeVisible();
  53 |   });
  54 | });
  55 | 
```