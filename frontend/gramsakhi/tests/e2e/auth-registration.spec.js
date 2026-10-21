import { test, expect } from '@playwright/test';
import { resolveOtp } from './helpers/otp.js';

const apiURL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
const devKey = process.env.OTP_DEV_RETRIEVAL_KEY || '';

function uniquePhone() {
  return `9${String(Date.now()).slice(-9)}`.slice(0, 10);
}

test('citizen registration reaches chat', async ({ page }) => {
  test.setTimeout(120_000);
  const health = await fetch(`${apiURL}/health`).then((r) => r.ok).catch(() => false);
  test.skip(!health, 'Backend not running');

  const phone = uniquePhone();
  await page.goto('/citizen/register');
  await page.getByRole('textbox').first().fill(phone);
  await page.getByRole('button', { name: /send otp|otp|verify/i }).click();
  await page.waitForURL(/verify-otp/);

  const otp = await resolveOtp({ apiURL, phone, devKey });
  const otpInputs = page.locator('input[inputmode="numeric"]');
  for (let i = 0; i < 6; i += 1) {
    await otpInputs.nth(i).fill(otp[i] || '');
  }
  await page.getByRole('button', { name: /verify|continue/i }).click();

  await page.waitForURL(/register|chat/, { timeout: 30_000 });
  if (page.url().includes('/register')) {
    await page.getByRole('button', { name: /create|register|complete/i }).click();
  }
  await expect(page).toHaveURL(/\/chat/, { timeout: 30_000 });
});
