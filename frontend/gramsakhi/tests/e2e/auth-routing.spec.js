import { test, expect } from '@playwright/test';
import {
  apiHealthOk,
  registerCitizenToChat,
  signOutFromProfile,
  loginCitizenViaOtp,
} from './helpers/journey.js';

test.describe('citizen auth routing contract', () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!(await apiHealthOk()), 'Backend API not reachable');
    await page.goto('/citizen/login');
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
  });

  test('A: /citizen/login shows auth UI even when JWT exists', async ({ page }) => {
    test.setTimeout(120_000);
    await registerCitizenToChat(page);
    expect(await page.evaluate(() => localStorage.getItem('accessToken'))).toBeTruthy();

    await page.goto('/citizen/login');
    await expect(page).toHaveURL(/\/citizen\/login/);
    await expect(page.getByText('Welcome back')).toBeVisible();
    await expect(page.getByRole('button', { name: /send otp/i })).toBeVisible();
    await expect(page).not.toHaveURL(/\/chat\/[0-9a-f-]+/i);
  });

  test('B: /citizen/register always shows registration UI', async ({ page }) => {
    await page.goto('/citizen/register');
    await expect(page.getByRole('button', { name: /send otp|otp|verify/i })).toBeVisible();
    const token = await page.evaluate(() => localStorage.getItem('accessToken'));
    expect(token).toBeFalsy();
  });

  test('C/D: /chat requires auth; logout clears session', async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto('/chat');
    await expect(page).toHaveURL(/\/citizen\/login/);

    const { phone } = await registerCitizenToChat(page);
    await expect(page).toHaveURL(/\/chat/);

    await signOutFromProfile(page);
    await page.goto('/chat');
    await expect(page).toHaveURL(/\/citizen\/login/);

    const token = await page.evaluate(() => localStorage.getItem('accessToken'));
    expect(token).toBeFalsy();

    await loginCitizenViaOtp(page, phone);
    await expect(page).toHaveURL(/\/chat/);
  });
});
