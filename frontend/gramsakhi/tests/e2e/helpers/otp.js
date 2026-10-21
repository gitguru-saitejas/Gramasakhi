import fs from 'node:fs';
import path from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, '../../../../../');
const OTP_MIRROR = path.join(REPO_ROOT, 'backend', '.dev_otp_last.txt');

export async function readDevOtpMirror(maxWaitMs = 15_000) {
  const start = Date.now();
  while (Date.now() - start < maxWaitMs) {
    try {
      const raw = fs.readFileSync(OTP_MIRROR, 'utf8');
      const m = raw.match(/OTP:\s*(\d{6})/);
      if (m) return m[1];
    } catch {
      // mirror not written yet
    }
    await sleep(250);
  }
  throw new Error(`Dev OTP mirror not found at ${OTP_MIRROR}`);
}

export async function fetchDevOtp(apiURL, phone, devKey) {
  if (!devKey) return null;
  const url = `${apiURL}/api/auth/otp/dev?phone_number=${encodeURIComponent(phone)}`;
  const res = await fetch(url, { headers: { 'X-Dev-OTP-Key': devKey } });
  if (!res.ok) return null;
  const data = await res.json();
  return data?.otp || null;
}

export async function resolveOtp({ apiURL, phone, devKey }) {
  const fromApi = await fetchDevOtp(apiURL, phone, devKey);
  if (fromApi) return fromApi;
  return await readDevOtpMirror();
}
