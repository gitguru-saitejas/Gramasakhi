#!/usr/bin/env node
/**
 * Phase 5 — Android golden journey static verification (architecture + contracts).
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(__dirname, '..');

const results = [];
let failures = 0;

function record(category, name, pass, evidence, kind = 'STATIC') {
  results.push({ category, name, pass, evidence, kind });
  if (!pass) failures += 1;
}

function read(rel) {
  return fs.readFileSync(path.join(MOBILE_ROOT, rel), 'utf8');
}

function exists(rel) {
  return fs.existsSync(path.join(MOBILE_ROOT, rel));
}

function testArchitecture() {
  record('arch', 'Expo SDK ~57', read('package.json').includes('"expo": "~57'), 'package.json', 'STATIC');
  record('arch', 'expo-router navigation', exists('app/_layout.tsx') && exists('app/chat.tsx'), 'app/', 'STATIC');
  record('arch', 'SecureStore auth tokens', read('src/storage/secureStorage.ts').includes('expo-secure-store'), 'secureStorage.ts', 'STATIC');
  record('arch', 'conversation id in SecureStore', read('src/storage/authTokens.ts').includes('CONVERSATION_ID_KEY'), 'authTokens.ts', 'STATIC');
  record('arch', 'ChatContext send guard', read('src/store/ChatContext.tsx').includes('sendInFlightRef'), 'ChatContext.tsx', 'STATIC');
  record('arch', 'TTS per-message context', read('src/context/TtsPlaybackContext.tsx').includes('activeMessageId'), 'TtsPlaybackContext.tsx', 'STATIC');
  record('arch', 'STT hook exists', exists('src/hooks/useVoiceInput.ts'), 'useVoiceInput.ts', 'STATIC');
  record(
    'api',
    'emulator API default 10.0.2.2',
    read('src/api/config.ts').includes('10.0.2.2') && read('app.config.ts').includes('10.0.2.2'),
    'config.ts + app.config.ts',
    'STATIC'
  );
  record(
    'api',
    'chat adapter maps answer + response_language',
    read('src/api/chatAdapter.ts').includes('response_language') && read('src/api/chatAdapter.ts').includes('mapBackendChatResponse'),
    'chatAdapter.ts',
    'STATIC'
  );
  record(
    'auth',
    'OTP registration on device',
    read('app/otp.tsx').includes('completeRegistration') && read('app/otp.tsx').includes('needsRegistration'),
    'otp.tsx',
    'STATIC'
  );
  record(
    'auth',
    'logout clears session',
    read('src/context/AuthContext.tsx').includes('clearAuthSession'),
    'AuthContext.tsx',
    'STATIC'
  );
  const i18n = read('src/i18n/strings.ts');
  record(
    'ui',
    'i18n kn/hi/en keys',
    i18n.includes('const kn:') && i18n.includes('const hi:') && i18n.includes('const en =') && i18n.includes('login.sendOtp'),
    'strings.ts',
    'STATIC'
  );
  record(
    'ui',
    'keyboard resize android',
    read('app.config.ts').includes("softwareKeyboardLayoutMode: 'resize'"),
    'app.config.ts',
    'STATIC'
  );
  record(
    'chat',
    'composer disabled while generating',
    read('src/components/chat/MessageComposer.tsx').includes('isGenerating'),
    'MessageComposer.tsx',
    'STATIC'
  );
  record(
    'chat',
    'Listen on assistant messages',
    read('src/components/chat/AssistantMessage.tsx').includes('playMessage'),
    'AssistantMessage.tsx',
    'STATIC'
  );
}

function testTypecheck() {
  try {
    execSync('npm run typecheck', { cwd: MOBILE_ROOT, stdio: 'pipe' });
    record('build', 'TypeScript typecheck', true, 'tsc --noEmit', 'COMMAND');
  } catch (e) {
    record('build', 'TypeScript typecheck', false, String(e.stderr || e.message).slice(0, 200), 'COMMAND');
  }
}

testArchitecture();
testTypecheck();

console.log('\n=== A6 Android Golden Journey (static) ===');
for (const r of results) {
  console.log(`${r.pass ? 'PASS' : 'FAIL'} [${r.category}] ${r.name} — ${r.evidence}`);
}
console.log(`\nTotal: ${results.length}, failures: ${failures}`);
process.exit(failures ? 1 : 0);
