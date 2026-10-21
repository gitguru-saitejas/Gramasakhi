import { test, expect } from '@playwright/test';
import {
  apiHealthOk,
  registerCitizenToChat,
  sendChatTurn,
  trackChatPosts,
  conversationIdFromStorage,
  conversationIdFromUrl,
  waitForConversationRoute,
  loginCitizenViaOtp,
  signOutFromProfile,
  chatComposer,
  chatSendButton,
  openFirstRecentConversation,
} from './helpers/journey.js';

test.describe('conversation persistence', () => {
  test.beforeEach(async () => {
    test.skip(!(await apiHealthOk()), 'Backend API not reachable');
  });

  test('refresh, navigation, and re-login preserve conversation', async ({ page }) => {
    test.setTimeout(420_000);
    await page.setViewportSize({ width: 1280, height: 800 });

    const { phone } = await registerCitizenToChat(page);
    const { records, detach } = trackChatPosts(page);

    await sendChatTurn(page, 'Tell me about Gruha Lakshmi.');
    const convId = records.at(-1)?.conversation_id || (await conversationIdFromStorage(page));
    expect(convId).toBeTruthy();

    await sendChatTurn(page, 'How can I apply?');
    expect(records.at(-1)?.conversation_id).toBe(convId);

    await waitForConversationRoute(page);
    const routeConvId = conversationIdFromUrl(page) || convId;
    const proseCountBefore = await page.locator('main .prose').count();

    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page).toHaveURL(new RegExp(`/chat/${routeConvId}`), { timeout: 60_000 });
    await expect(chatComposer(page)).toBeEnabled({ timeout: 60_000 });
    await expect(page.locator('main .prose').first()).not.toHaveText('', { timeout: 120_000 });
    expect(await page.locator('main .prose').count()).toBeGreaterThanOrEqual(
      Math.max(proseCountBefore, 1)
    );

    await sendChatTurn(page, 'Documents?');
    expect(records.at(-1)?.conversation_id).toBe(convId);

    await page.goto('/citizen/login');
    await expect(page.getByText('Welcome back')).toBeVisible();
    await expect(page).toHaveURL(/\/citizen\/login/);

    await page.goto('/chat');
    await expect(chatComposer(page)).toBeEnabled({ timeout: 30_000 });

    await signOutFromProfile(page);
    await loginCitizenViaOtp(page, phone);

    await openFirstRecentConversation(page);
    expect(page.url()).toContain(routeConvId);
    await expect(page.locator('.prose').first()).not.toHaveText('', { timeout: 60_000 });

    detach();
  });

  test('controlled chat failure recovers Send lifecycle', async ({ page }) => {
    test.setTimeout(180_000);
    await page.setViewportSize({ width: 1280, height: 800 });
    await registerCitizenToChat(page);

    let failOnce = true;
    await page.route('**/api/chat', async (route) => {
      if (failOnce && route.request().method() === 'POST') {
        failOnce = false;
        await route.abort('failed');
        return;
      }
      await route.continue();
    });

    const composer = chatComposer(page);
    await composer.fill('Tell me about Gruha Lakshmi.');
    await chatSendButton(page).click();
    await expect(page.getByRole('alert').first()).toBeVisible({ timeout: 30_000 });
    await expect(composer).toBeEnabled({ timeout: 30_000 });

    await composer.fill('Tell me about Gruha Lakshmi.');
    await expect(chatSendButton(page)).toBeEnabled({ timeout: 15_000 });
    await chatSendButton(page).click();
    await expect(page.getByText(/Sakhi is analyzing/i)).toBeVisible({ timeout: 15_000 }).catch(() => {});
    await expect(page.getByText(/Sakhi is analyzing/i)).toHaveCount(0, { timeout: 180_000 });
    await expect(page.locator('.prose').last()).not.toHaveText('', { timeout: 15_000 });
  });
});
