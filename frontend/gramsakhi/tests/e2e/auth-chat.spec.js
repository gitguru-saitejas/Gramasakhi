import { test, expect } from '@playwright/test';

import {

  apiHealthOk,

  registerCitizenToChat,

  sendChatTurn,

  trackChatPosts,

  listenButtons,

} from './helpers/journey.js';



test.describe('citizen auth + chat smoke', () => {

  test.beforeEach(async () => {

    test.skip(!(await apiHealthOk()), 'Backend API not reachable at PLAYWRIGHT_API_URL');

  });



  test('register, login, multi-turn chat, language transform', async ({ page }) => {

    test.setTimeout(300_000);

    const consoleErrors = [];

    const chatResponses = [];

    page.on('console', (msg) => {

      if (msg.type() === 'error') consoleErrors.push(msg.text());

    });

    page.on('pageerror', (err) => consoleErrors.push(String(err)));

    page.on('response', async (res) => {

      if (!res.url().includes('/api/chat') || res.request().method() !== 'POST') return;

      let body = '';

      try {

        body = await res.text();

      } catch {

        body = '<unreadable>';

      }

      chatResponses.push({ status: res.status(), body: body.slice(0, 500) });

    });



    await registerCitizenToChat(page);



    const turns = ['Tell me about Gruha Lakshmi.', 'How can I apply?', 'Kannada please'];

    const { records } = trackChatPosts(page);



    for (const q of turns) {

      const proseCountBefore = await page.locator('main .prose').count();

      await sendChatTurn(page, q);

      const proseCountAfter = await page.locator('main .prose').count();

      expect(proseCountAfter).toBeGreaterThanOrEqual(Math.max(proseCountBefore, 1));

    }



    expect(chatResponses.length).toBeGreaterThanOrEqual(turns.length);

    for (const r of chatResponses.slice(0, turns.length)) {

      expect(r.status).toBeGreaterThanOrEqual(200);

      expect(r.status).toBeLessThan(300);

    }

    expect(records.length).toBeGreaterThanOrEqual(turns.length);



    const listen = listenButtons(page);

    const count = await listen.count();

    expect(count).toBeGreaterThan(0);

    if (count >= 2) {

      await listen.nth(count - 1).click();

      await page.waitForTimeout(1500);

      await listen.nth(count - 2).click();

      await expect(page.getByText(/Voice playback is not available/i)).toHaveCount(0);

    }



    if (consoleErrors.length) {

      test.info().attach('console-errors', {

        body: consoleErrors.join('\n'),

        contentType: 'text/plain',

      });

    }

  });

});

