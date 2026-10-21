import { expect } from '@playwright/test';
import { resolveOtp } from './otp.js';

export const apiURL = process.env.PLAYWRIGHT_API_URL || 'http://127.0.0.1:8000';
export const devKey = process.env.OTP_DEV_RETRIEVAL_KEY || '';

export function uniquePhone() {
  const suffix = String(Date.now()).slice(-9);
  return `9${suffix}`.slice(0, 10);
}

export async function apiHealthOk() {
  try {
    const r = await fetch(`${apiURL}/health`, { signal: AbortSignal.timeout(5000) });
    return r.ok;
  } catch {
    return false;
  }
}

/** Chat composer send — avoids matching auth "Send OTP". */
export function chatSendButton(page) {
  return page.getByRole('button', { name: 'Send Message' });
}

export function chatComposer(page) {
  return page.locator('main').getByRole('textbox').first();
}

/** Attach listener; returns { records, detach }. */
export function trackChatPosts(page) {
  const records = [];
  const handler = async (res) => {
    if (!res.url().includes('/api/chat') || res.request().method() !== 'POST') return;
    let body = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    records.push({
      status: res.status(),
      conversation_id: body?.conversation_id ? String(body.conversation_id) : null,
      answer: body?.answer || '',
      response_language: body?.response_language || null,
      language_operation: body?.language_operation || null,
      detected_scheme: body?.detected_scheme || body?.active_scheme_context || null,
      citizen_intent: body?.citizen_intent || null,
      nlu_intent: body?.nlu_intent || null,
    });
  };
  page.on('response', handler);
  return {
    records,
    detach: () => page.off('response', handler),
  };
}

export async function waitForAssistantTurn(page, { timeoutMs = 180_000 } = {}) {
  const analyzing = page.getByText(/Sakhi is analyzing/i);
  await analyzing.waitFor({ state: 'visible', timeout: 15_000 }).catch(() => {});
  await expect(analyzing).toHaveCount(0, { timeout: timeoutMs });
  const prose = page.locator('main .prose').last();
  await expect(prose).not.toHaveText('', { timeout: 15_000 });
  await expect(chatComposer(page)).toBeEnabled({ timeout: 15_000 });
}

export async function sendChatTurn(page, text, { timeoutMs = 180_000 } = {}) {
  const composer = chatComposer(page);
  await expect(composer).toBeEnabled({ timeout: 30_000 });
  await composer.fill(text);
  await expect(composer).toHaveValue(text);
  const sendBtn = chatSendButton(page);
  await expect(sendBtn).toBeEnabled({ timeout: 15_000 });
  await sendBtn.click();
  await waitForAssistantTurn(page, { timeoutMs });
}

export async function fillOtp(page, otp) {
  const otpInputs = page.locator('input[inputmode="numeric"]');
  for (let i = 0; i < 6; i += 1) {
    await otpInputs.nth(i).fill(otp[i] || '');
  }
}

export async function registerCitizenToChat(page, { displayName = 'Golden Citizen' } = {}) {
  const phone = uniquePhone();
  await page.goto('/citizen/register');
  await page.getByRole('textbox').first().fill(phone);
  await page.getByRole('button', { name: /send otp|otp|verify/i }).click();
  await page.waitForURL(/verify-otp/);

  const otp = await resolveOtp({ apiURL, phone, devKey });
  await fillOtp(page, otp);
  await expect(page.getByRole('button', { name: /verify|continue/i })).toBeEnabled();
  await page.getByRole('button', { name: /verify|continue/i }).click();

  await page.waitForURL(/register|chat/, { timeout: 60_000 });
  if (page.url().includes('/register')) {
    const nameInput = page.getByPlaceholder(/name|display/i);
    if (await nameInput.count()) {
      await nameInput.fill(displayName);
    }
    await page.getByRole('button', { name: /create|register|complete/i }).click();
  }
  await page.waitForURL(/\/chat/, { timeout: 60_000 });
  await expect(chatComposer(page)).toBeEnabled({ timeout: 60_000 });
  return { phone };
}

export async function loginCitizenViaOtp(page, phone) {
  await page.goto('/citizen/login');
  await expect(page.getByText('Welcome back')).toBeVisible();
  await page.getByRole('textbox').first().fill(phone);
  await page.getByRole('button', { name: /send otp/i }).click();
  await page.waitForURL(/verify-otp/);
  const otp = await resolveOtp({ apiURL, phone, devKey });
  await fillOtp(page, otp);
  await page.getByRole('button', { name: /verify|continue/i }).click();
  await page.waitForURL(/\/chat/, { timeout: 60_000 });
}

export async function openProfileModal(page) {
  const mobileProfile = page.getByRole('button', { name: /profile and settings/i });
  if (await mobileProfile.isVisible().catch(() => false)) {
    await mobileProfile.click();
  } else {
    const citizenCard = page.locator('aside [role="button"]').filter({ hasText: /Citizen/i });
    await expect(citizenCard.first()).toBeVisible({ timeout: 10_000 });
    await citizenCard.first().click();
  }
  await expect(page.getByRole('heading', { name: /citizen profile/i })).toBeVisible({
    timeout: 10_000,
  });
}

export async function signOutFromProfile(page) {
  await openProfileModal(page);
  await page.getByRole('button', { name: /sign out/i }).click();
}

export function listenButtons(page) {
  return page.getByRole('button', {
    name: /listen|audio|ಕೇಳ|सुन|stop|volume/i,
  });
}

export async function assertComposerChrome(page) {
  await expect(chatComposer(page)).toBeVisible();
  await expect(chatSendButton(page)).toBeVisible();
  await expect(page.getByRole('button', { name: /voice input|stop recording/i })).toBeVisible();
}

export function conversationIdFromStorage(page) {
  return page.evaluate(() => localStorage.getItem('gramsakhiConversationId'));
}

export function conversationIdFromUrl(page) {
  const m = page.url().match(/\/chat\/([0-9a-f-]+)/i);
  return m ? m[1] : null;
}

export async function waitForConversationRoute(page, { timeoutMs = 60_000 } = {}) {
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/i, { timeout: timeoutMs });
}

export function recentConversationButtons(page) {
  return page.locator('aside button').filter({ has: page.locator('span.truncate') });
}

export async function openFirstRecentConversation(page) {
  await expect(page.locator('aside').getByText(/^loading/i)).toHaveCount(0, { timeout: 60_000 }).catch(
    () => {}
  );
  const items = recentConversationButtons(page);
  await expect(items.first()).toBeVisible({ timeout: 60_000 });
  await items.first().click();
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]+/i, { timeout: 30_000 });
}
