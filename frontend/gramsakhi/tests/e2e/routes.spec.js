import { test, expect } from '@playwright/test';

const CITIZEN_ROUTES = [
  '/',
  '/citizen/login',
  '/citizen/register',
  '/citizen/verify-otp',
  '/chat',
];

const VIEWPORTS = [
  { width: 375, height: 812, name: 'mobile' },
  { width: 768, height: 1024, name: 'tablet' },
  { width: 1280, height: 800, name: 'desktop' },
];

for (const route of CITIZEN_ROUTES) {
  test(`route ${route} renders without fatal errors`, async ({ page }) => {
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    const res = await page.goto(route, { waitUntil: 'domcontentloaded' });
    expect(res?.status()).toBeLessThan(500);
    await expect(page.locator('body')).toBeVisible();
    const bodyText = await page.locator('body').innerText();
    expect(bodyText.trim().length).toBeGreaterThan(0);
    expect(errors.filter((e) => !/ResizeObserver|Non-Error/i.test(e))).toEqual([]);
  });
}

test.describe('chat composer UI audit', () => {
  for (const vp of VIEWPORTS) {
    test(`composer controls at ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto('/citizen/login', { waitUntil: 'domcontentloaded' });
      const paperclip = page.locator('[aria-label*="attach"], [title*="attach"], button:has(svg.lucide-paperclip)');
      await expect(paperclip).toHaveCount(0);
    });
  }
});

test('/chat redirects unauthenticated users', async ({ page }) => {
  await page.goto('/chat', { waitUntil: 'domcontentloaded' });
  await expect(page).toHaveURL(/\/citizen\/login/);
});
