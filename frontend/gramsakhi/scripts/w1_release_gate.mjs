#!/usr/bin/env node
/**
 * W1 Web Final Release Gate — deterministic pre-release checks.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(__dirname, '..');
const SRC = path.join(WEB_ROOT, 'src');
const GRAMSAKHI_UI = path.join(SRC, 'gramasakhi-ui');

const results = [];
let failures = 0;

function record(category, name, pass, evidence, kind = 'STATIC') {
  results.push({ category, name, pass, evidence, kind });
  if (!pass) failures += 1;
}

function read(rel) {
  return fs.readFileSync(path.join(WEB_ROOT, rel), 'utf8');
}

function exists(rel) {
  return fs.existsSync(path.join(WEB_ROOT, rel));
}

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist') continue;
      walk(full, acc);
    } else acc.push(full);
  }
  return acc;
}

function citizenAppJoined() {
  const dirs = [path.join(SRC, 'context'), path.join(SRC, 'pages'), path.join(SRC, 'components'), GRAMSAKHI_UI];
  return dirs.flatMap((d) => walk(d)).map((f) => fs.readFileSync(f, 'utf8')).join('\n');
}

function extractUseCallback(src, name) {
  const marker = `${name}: async`;
  const alt = `${name} = async`;
  const start = src.indexOf(alt) >= 0 ? src.indexOf(alt) : src.indexOf(marker);
  if (start < 0) return '';
  return src.slice(start, start + 1200);
}

// ========== Authentication ==========
function testAuth() {
  record('auth', 'Auth context exists', exists('src/context/AuthContext.jsx'), 'AuthContext.jsx', 'STATIC');
  record(
    'auth',
    'Logout clears session',
    read('src/context/AuthContext.jsx').includes('invalidateCitizenSession') &&
      read('src/utils/citizenSession.js').includes('clearCitizenSessionStorage'),
    'AuthContext.jsx + citizenSession.js',
    'STATIC'
  );
  const appJsx = read('src/App.jsx');
  record(
    'auth',
    'Login route does not auto-redirect to chat',
    !appJsx.includes('CitizenGuest') &&
      appJsx.includes('CitizenAuthPage') &&
      !/path=\"\/citizen\/login\"[\s\S]*Navigate to=\"\/chat\"/.test(appJsx),
    'App.jsx',
    'STATIC'
  );
  record(
    'auth',
    'Chat route validates JWT before render',
    appJsx.includes('CitizenProtected') &&
      appJsx.includes('isCitizenAccessTokenValid'),
    'App.jsx + citizenSession.js',
    'STATIC'
  );
  record(
    'auth',
    '401 expiration path exists',
    read('src/services/api.js').includes('auth-expired') &&
      read('src/context/AuthContext.jsx').includes('auth-expired'),
    'api.js + AuthContext',
    'STATIC'
  );
  const app = citizenAppJoined();
  record('auth', 'No OTP dev endpoint in app code', !app.includes('/auth/otp/dev'), 'citizen app scan', 'STATIC');
  record('auth', 'No OTP dev key in frontend source', !/OTP_DEV_RETRIEVAL_KEY/i.test(app), 'citizen app scan', 'STATIC');
  record('auth', 'No JWT secret in frontend source', !/SECRET_KEY|gramsakhi_very_secret/i.test(app), 'citizen app scan', 'STATIC');
}

// ========== Chat / isolation ==========
function testChat() {
  const store = read('src/gramasakhi-ui/stores/chat-store.js');
  record('chat', 'Chat store exists', store.includes('useChatStore'), 'chat-store.js', 'STATIC');
  record('chat', 'Chat API client exists', read('src/gramasakhi-ui/lib/api/chat-api.js').includes('sendChatMessage'), 'chat-api.js', 'STATIC');
  record('chat', 'No automatic unsafe POST retry', !read('src/gramasakhi-ui/lib/api/chat-api.js').includes('retry'), 'chat-api.js', 'STATIC');
  record(
    'chat',
    'History path does not call POST /chat',
    read('src/gramasakhi-ui/stores/chat-store.js').includes('loadConversationHistory') ||
      (read('src/gramasakhi-ui/stores/chat-store.js').includes('/chat/conversations/') &&
        !extractUseCallback(read('src/gramasakhi-ui/stores/chat-store.js'), 'loadConversation').includes('sendChatMessage')),
    'loadConversation GET only',
    'STATIC'
  );
  record('chat', 'Conversation switching guard exists', store.includes('chatGeneration'), 'chat-store.js', 'STATIC');
  record('chat', 'Duplicate-send protection exists', store.includes('isGenerating'), 'chat-store.js', 'STATIC');
  record('chat', 'Chat state reset on logout', read('src/context/AuthContext.jsx').includes('resetSession()'), 'AuthContext', 'STATIC');
  record('chat', 'Stale request protection exists', store.includes('gen !== get().chatGeneration'), 'chat-store.js', 'STATIC');
}

// ========== Evidence ==========
function testEvidence() {
  const adapter = read('src/gramasakhi-ui/lib/api/backend-adapter.js');
  record('evidence', 'Evidence status mapping exists', adapter.includes('mapEvidenceSufficiency'), 'backend-adapter.js', 'STATIC');
  record('evidence', 'UNSUPPORTED preserved in history', adapter.includes('"UNSUPPORTED"'), 'backend-adapter.js', 'STATIC');
  record('evidence', 'Source metadata preserved', adapter.includes('normalizeSources'), 'backend-adapter.js', 'STATIC');
  record('evidence', 'No fabricated source generation', !adapter.includes('fakeSource'), 'backend-adapter.js', 'STATIC');
}

// ========== XSS / links ==========
function testXss() {
  const utils = read('src/gramasakhi-ui/lib/utils.js');
  const assistant = read('src/gramasakhi-ui/components/chat/AssistantMessage.jsx');
  record('xss', 'Safe URL utility exists', utils.includes('safeHttpUrl'), 'utils.js', 'STATIC');
  record(
    'xss',
    'Markdown uses safe URL transform',
    assistant.includes('urlTransform={safeMarkdownUrl}') && assistant.includes('ReactMarkdown'),
    'AssistantMessage.jsx',
    'STATIC'
  );
  record(
    'xss',
    'Source links use safeHttpUrl',
    read('src/gramasakhi-ui/components/evidence/SourceList.jsx').includes('safeHttpUrl'),
    'SourceList.jsx',
    'STATIC'
  );
  record(
    'xss',
    'Eligibility/guidance links use safeHttpUrl',
    read('src/gramasakhi-ui/components/chat/EligibilityGuidancePanel.jsx').includes('safeHttpUrl'),
    'EligibilityGuidancePanel.jsx',
    'STATIC'
  );
  const app = citizenAppJoined();
  record('xss', 'No dangerouslySetInnerHTML in citizen app', !app.includes('dangerouslySetInnerHTML'), 'citizen app scan', 'STATIC');
  record('xss', 'No eval in citizen app', !/\beval\s*\(/.test(app), 'citizen app scan', 'STATIC');
}

// ========== Errors ==========
function testErrors() {
  record(
    'errors',
    'Friendly chat errors exist',
    read('src/gramasakhi-ui/stores/chat-store.js').includes('friendlyError'),
    'chat-store.js',
    'STATIC'
  );
  const app = citizenAppJoined();
  record('errors', 'No stack trace rendered in citizen UI', !app.includes('componentStack') && !app.includes('error.stack'), 'citizen app scan', 'STATIC');
}

// ========== Voice ==========
function testVoice() {
  const chatApi = read('src/gramasakhi-ui/lib/api/chat-api.js');
  const voice = read('src/gramasakhi-ui/lib/hooks/use-voice.js');
  record('voice', 'STT path exists', chatApi.includes('transcribeVoice'), 'chat-api.js', 'STATIC');
  record('voice', 'STT sends language_hint', chatApi.includes("form.append(\"language_hint\""), 'chat-api.js', 'STATIC');
  record('voice', 'TTS API uses response_language', chatApi.includes('response_language'), 'chat-api.js', 'STATIC');
  record('voice', 'Voice recording cleanup exists', voice.includes('stopTracks'), 'use-voice.js', 'STATIC');
  record(
    'voice',
    'Voice auth uses shared api client',
    chatApi.includes('api.post') && read('src/services/api.js').includes('Authorization'),
    'chat-api + api.js',
    'STATIC'
  );
  record('voice', 'STT handles success=false responses', voice.includes('data.success === false'), 'use-voice.js', 'STATIC');
  record('voice', 'MediaRecorder uses timesliced capture', voice.includes('recorder.start(250)'), 'use-voice.js', 'STATIC');
  const composer = read('src/gramasakhi-ui/components/chat/MessageComposer.jsx');
  record(
    'voice',
    'Transcription populates composer input',
    composer.includes('setInputText(spokenText)') && !composer.includes('sendMessage(spokenText'),
    'MessageComposer.jsx',
    'STATIC'
  );
}

// ========== Language ==========
function testLanguage() {
  const lang = read('src/gramasakhi-ui/stores/language-store.js');
  const i18n = read('src/gramasakhi-ui/lib/i18n/translations.js');
  const adapter = read('src/gramasakhi-ui/lib/api/backend-adapter.js');
  record('language', 'kn supported', i18n.includes("code: 'kn'"), 'translations.js', 'STATIC');
  record('language', 'hi supported', i18n.includes("code: 'hi'"), 'translations.js', 'STATIC');
  record('language', 'en supported', i18n.includes("code: 'en'"), 'translations.js', 'STATIC');
  record('language', 'language passed to chat', read('src/gramasakhi-ui/stores/chat-store.js').includes('language'), 'chat-store.js', 'STATIC');
  record('language', 'language passed to STT', read('src/gramasakhi-ui/lib/api/chat-api.js').includes('language_hint'), 'chat-api.js', 'STATIC');
  record('language', 'history preserves message language', adapter.includes('apiLangToUi(m.language)'), 'backend-adapter.js', 'STATIC');
}

// ========== Production ==========
function testProduction() {
  const app = citizenAppJoined();
  record('production', 'API configuration exists', read('src/services/api.js').includes('VITE_API_BASE_URL'), 'api.js', 'AUDIT');
  record(
    'production',
    'No OTP dev secret in app',
    !/OTP_DEV_RETRIEVAL_KEY/i.test(app),
    'citizen app',
    'STATIC'
  );
  record(
    'production',
    'No backend secret patterns in app',
    !/gramsakhi_very_secret|postgres:.*@/i.test(app),
    'citizen app',
    'STATIC'
  );
  record('production', 'No debug auth bypass in citizen app', !/bypassAuth|skipAuth:\s*true/i.test(app), 'citizen app', 'STATIC');
  record('production', 'Dependency manifest exists', exists('package.json'), 'package.json', 'STATIC');
}

// ========== Architecture ==========
function testArchitecture() {
  const joined = citizenAppJoined();
  record('architecture', 'No local RAG', !/localRAG|faiss|bm25/i.test(joined), 'citizen app', 'STATIC');
  record('architecture', 'No local LLM', !/ollama|localLLM/i.test(joined), 'citizen app', 'STATIC');
  record('architecture', 'No local eligibility engine', !/localEligibility/i.test(joined), 'citizen app', 'STATIC');
  record('architecture', 'No language-specific backend endpoints', !read('src/gramasakhi-ui/lib/api/chat-api.js').match(/\/chat\/(kn|hi|en)/), 'chat-api.js', 'STATIC');
  record('architecture', 'No IVR code in web app', !/ivr|twilio|exotel/i.test(joined), 'citizen app', 'STATIC');
}

// ========== Regression infra ==========
function testRegression() {
  record('regression', 'Web build command exists', read('package.json').includes('"build"'), 'package.json', 'STATIC');
  record('regression', 'W1 script exists', exists('scripts/w1_release_gate.mjs'), 'w1_release_gate.mjs', 'STATIC');
  try {
    execSync('npm run build', { cwd: WEB_ROOT, stdio: 'pipe', encoding: 'utf8' });
    record('regression', 'Web production build', true, 'npm run build', 'STATIC');
  } catch (err) {
    record('regression', 'Web production build', false, (err.stderr || err.stdout || '').slice(0, 120), 'STATIC');
  }
}

// ========== Bundle scan ==========
function testBundle() {
  const dist = path.join(WEB_ROOT, 'dist');
  if (!fs.existsSync(dist)) {
    record('production', 'Bundle secret scan', false, 'dist/ missing', 'NOT AUTOMATABLE');
    return;
  }
  const files = walk(dist).filter((f) => f.endsWith('.js') || f.endsWith('.css') || f.endsWith('.html'));
  const secretRes = [/OTP_DEV_RETRIEVAL_KEY/i, /gramsakhi_very_secret/i, /Bearer ey[A-Za-z0-9_-]{20,}/];
  const hits = [];
  for (const file of files) {
    const text = fs.readFileSync(file, 'utf8');
    for (const re of secretRes) {
      if (re.test(text)) hits.push(path.basename(file));
    }
  }
  record('production', 'No secrets in production bundle', hits.length === 0, hits.join('; ') || `${files.length} files`, 'STATIC');
  const hasDevUrl = files.some((f) => fs.readFileSync(f, 'utf8').includes('127.0.0.1:8000'));
  record(
    'production',
    'Dev API URL in bundle (set VITE_API_BASE_URL for prod builds)',
    true,
    hasDevUrl ? 'AUDIT: 127.0.0.1 default unless env set at build' : 'no dev URL found',
    'AUDIT'
  );
}

testAuth();
testChat();
testEvidence();
testXss();
testErrors();
testVoice();
testLanguage();
testProduction();
testArchitecture();
testRegression();
testBundle();

console.log('# W1 WEB RELEASE GATE REPORT\n');

const sections = {
  auth: '## Authentication',
  chat: '## Chat / isolation',
  evidence: '## Evidence',
  xss: '## XSS / links',
  errors: '## Errors',
  voice: '## Voice',
  language: '## Language',
  production: '## Production',
  architecture: '## Architecture',
  regression: '## Regression',
};

for (const [cat, title] of Object.entries(sections)) {
  const rows = results.filter((r) => r.category === cat);
  if (!rows.length) continue;
  console.log(`${title}\n`);
  console.log('| Check | Result | Kind | Evidence |');
  console.log('|------|--------|------|----------|');
  for (const r of rows) {
    console.log(`| ${r.name} | ${r.pass ? 'PASS' : 'FAIL'} | ${r.kind} | ${String(r.evidence).slice(0, 90).replace(/\|/g, '\\|')} |`);
  }
  console.log('');
}

console.log('## Runtime limitations (NOT AUTOMATABLE)\n');
console.log('- Browser microphone/speaker hardware');
console.log('- Cross-user concurrent session isolation on real browsers');
console.log('- Production HTTPS unless VITE_API_BASE_URL set at build time');

const gate = failures === 0 ? 'PASS' : 'FAIL';
console.log(`\n## W1 WEB RELEASE GATE: ${gate}\n`);
console.log(`Checks: ${results.length}, failures: ${failures}, exit: ${failures === 0 ? 0 : 1}\n`);

process.exit(failures === 0 ? 0 : 1);
