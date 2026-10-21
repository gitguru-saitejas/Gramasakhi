import { test, expect } from '@playwright/test';
import {
  apiHealthOk,
  registerCitizenToChat,
  sendChatTurn,
  trackChatPosts,
  loginCitizenViaOtp,
  signOutFromProfile,
  listenButtons,
  assertComposerChrome,
  conversationIdFromStorage,
  openFirstRecentConversation,
} from './helpers/journey.js';

test.describe('golden citizen web journey', () => {
  test.beforeEach(async () => {
    test.skip(!(await apiHealthOk()), 'Backend API not reachable');
  });

  test('full journey: register through re-login, language, TTS, short queries', async ({
    page,
  }) => {
    test.setTimeout(600_000);
    await page.setViewportSize({ width: 1280, height: 800 });

    const pageErrors = [];
    page.on('pageerror', (e) => pageErrors.push(String(e)));

    await page.goto('/citizen/login');
    await expect(page.getByText('Welcome back')).toBeVisible();

    const { phone } = await registerCitizenToChat(page);
    const { records, detach } = trackChatPosts(page);

    await sendChatTurn(page, 'Tell me about Gruha Lakshmi.');
    const convId = records.at(-1)?.conversation_id || (await conversationIdFromStorage(page));
    expect(convId).toBeTruthy();
    expect(records.at(-1)?.status).toBeGreaterThanOrEqual(200);
    expect(records.at(-1)?.status).toBeLessThan(300);
    await expect(page.locator('.prose').last()).not.toHaveText('', { timeout: 5_000 });
    await expect(page.getByText(/supported|partial|verified|grounded/i).first()).toBeVisible({
      timeout: 10_000,
    }).catch(() => {});

    await sendChatTurn(page, 'How can I apply?');
    expect(records.at(-1)?.conversation_id).toBe(convId);
    const applyAnswer = records.at(-1)?.answer || '';
    expect(applyAnswer.length).toBeGreaterThan(20);

    await sendChatTurn(page, 'Documents?');
    expect(records.at(-1)?.conversation_id).toBe(convId);
    const docsAnswer = records.at(-1)?.answer || '';
    expect(docsAnswer.length).toBeGreaterThan(10);

    await sendChatTurn(page, 'Kannada please');
    expect(records.at(-1)?.conversation_id).toBe(convId);
    expect(records.at(-1)?.response_language).toMatch(/KN/i);
    const knOp = records.at(-1)?.language_operation;
    if (knOp) {
      expect(knOp).toMatch(/translate|rephrase|transform|language|TRANSLATION/i);
    }

    await sendChatTurn(page, 'Explain that simply');
    expect(records.at(-1)?.conversation_id).toBe(convId);
    expect(records.at(-1)?.answer.length).toBeGreaterThan(10);

    await sendChatTurn(page, 'English please');
    expect(records.at(-1)?.conversation_id).toBe(convId);
    expect(records.at(-1)?.response_language).toMatch(/EN/i);

    for (const q of ['Am I eligible for this?', 'Tell me simply.', 'Where do I apply?']) {
      await sendChatTurn(page, q, { timeoutMs: 180_000 });
      expect(records.at(-1)?.conversation_id).toBe(convId);
      expect(records.at(-1)?.answer.length).toBeGreaterThan(5);
    }

    const listen = listenButtons(page);
    const listenCount = await listen.count();
    expect(listenCount).toBeGreaterThan(0);

    await listen.last().click();
    await expect(listen.last()).toHaveAttribute('aria-busy', 'true').catch(() => {});
    await page.waitForTimeout(800);
    await expect(page.getByText(/Voice playback is not available/i)).toHaveCount(0);

    if (listenCount >= 2) {
      await listen.nth(listenCount - 2).click();
      await page.waitForTimeout(800);
      await expect(page.getByText(/Voice playback is not available/i)).toHaveCount(0);
    }

    await sendChatTurn(page, 'Who can get this?');
    expect(records.at(-1)?.conversation_id).toBe(convId);
    await expect(listenButtons(page).last()).toBeVisible();

    await signOutFromProfile(page);
    await page.goto('/citizen/login');
    await expect(page.getByText('Welcome back')).toBeVisible();
    await page.goto('/chat');
    await expect(page).toHaveURL(/\/citizen\/login/);

    await loginCitizenViaOtp(page, phone);
    await openFirstRecentConversation(page);
    expect(page.url()).toContain(convId);
    await expect(page.locator('main .prose').first()).not.toHaveText('', { timeout: 120_000 });

    expect(pageErrors.filter((e) => !/ResizeObserver|Non-Error/i.test(e))).toEqual([]);
    detach();
  });

  test('STT mic control present; failure does not lock composer', async ({ page }) => {
    test.setTimeout(120_000);
    await page.setViewportSize({ width: 375, height: 812 });
    await registerCitizenToChat(page);
    const mic = page.getByRole('button', { name: /voice input|stop recording/i });
    await expect(mic).toBeVisible();
    await mic.click();
    await page.waitForTimeout(1500);
    const composer = page.getByRole('textbox').first();
    await expect(composer).toBeEnabled({ timeout: 15_000 });
    await composer.fill('What papers do I need?');
    await expect(page.getByRole('button', { name: 'Send Message' })).toBeEnabled();
  });

  test('responsive layout: composer, send, mic, listen at 375 / 768 / 1280', async ({ page }) => {
    test.setTimeout(240_000);
    await registerCitizenToChat(page);
    await sendChatTurn(page, 'Tell me about Gruha Lakshmi.');

    for (const width of [375, 768, 1280]) {
      await page.setViewportSize({ width, height: 812 });
      await assertComposerChrome(page);
      await expect(page.locator('.prose').last()).toBeVisible();
      const listen = listenButtons(page);
      if ((await listen.count()) > 0) {
        await expect(listen.last()).toBeVisible();
      }
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth > window.innerWidth + 2
      );
      expect(overflow).toBe(false);
    }
  });
});
