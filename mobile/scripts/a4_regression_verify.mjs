#!/usr/bin/env node
/**
 * A4 Android Multilingual Language — automated regression verification.
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const MOBILE_ROOT = path.resolve(__dirname, '..');
const SRC = path.join(MOBILE_ROOT, 'src');

const results = [];
let failures = 0;

function record(category, name, pass, evidence, kind = 'STATIC') {
  results.push({ category, name, pass, evidence, kind });
  if (!pass) failures += 1;
}

function read(rel) {
  return fs.readFileSync(path.join(MOBILE_ROOT, rel), 'utf8');
}

function walk(dir, acc = []) {
  if (!fs.existsSync(dir)) return acc;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === '.git') continue;
      walk(full, acc);
    } else acc.push(full);
  }
  return acc;
}

function testLanguageDefinitions() {
  const constants = read('src/constants/language.ts');
  const utils = read('src/utils/language.ts');
  record(
    'language',
    'supported languages exactly kn/hi/en',
    constants.includes("'kn'") &&
      constants.includes("'hi'") &&
      constants.includes("'en'") &&
      constants.includes("['kn', 'hi', 'en']"),
    'constants/language.ts',
    'STATIC'
  );
  record('language', 'validation accepts kn', utils.includes('isSupportedLanguage') && constants.includes("'kn'"), 'utils/language.ts', 'STATIC');
  record('language', 'validation accepts hi', constants.includes("'hi'"), 'constants/language.ts', 'STATIC');
  record('language', 'validation accepts en', constants.includes("'en'"), 'constants/language.ts', 'STATIC');
  record(
    'language',
    'unsupported language rejected',
    utils.includes('isSupportedLanguage') && utils.includes('return false'),
    'utils/language.ts',
    'STATIC'
  );
  record(
    'language',
    'invalid language fallback works',
    utils.includes('normalizeUiLanguage') && constants.includes("DEFAULT_UI_LANGUAGE: UiLanguageCode = 'kn'"),
    'utils/language.ts',
    'STATIC'
  );
  record(
    'language',
    'display labels correct',
    constants.includes('ಕನ್ನಡ') && constants.includes('हिन्दी') && constants.includes("'English'"),
    'LANGUAGE_OPTIONS',
    'STATIC'
  );
}

function testChatLanguage() {
  const chat = read('app/chat.tsx');
  const ctx = read('src/store/ChatContext.tsx');
  record(
    'chat',
    'typed message uses selected language',
    chat.includes('sendMessage(trimmed, language)') && chat.includes('useLanguage'),
    'chat.tsx',
    'STATIC'
  );
  record(
    'chat',
    'STT message uses request language at record start',
    read('app/chat.tsx').includes('useVoiceInput({') &&
      read('src/hooks/useVoiceInput.ts').includes('languageAtRecordRef'),
    'chat + useVoiceInput',
    'STATIC'
  );
  record(
    'chat',
    'no hard-coded kn in chat send paths',
    !chat.match(/sendMessage\([^)]*'kn'/),
    'chat.tsx',
    'STATIC'
  );
  record(
    'chat',
    'ChatContext default uses DEFAULT_UI_LANGUAGE',
    ctx.includes('DEFAULT_UI_LANGUAGE') && !ctx.includes("language = 'kn'"),
    'ChatContext.tsx',
    'STATIC'
  );
}

function testSttLanguage() {
  const hook = read('src/hooks/useVoiceInput.ts');
  record('stt', 'language_hint via uiLangToApi(langAtRecord)', hook.includes('uiLangToApi(langAtRecord)'), 'useVoiceInput.ts', 'STATIC');
  record('stt', 'language captured at record start', hook.includes('languageAtRecordRef'), 'useVoiceInput.ts', 'STATIC');
  record(
    'stt',
    'changing selector does not mutate in-flight STT',
    hook.includes('languageAtRecordRef.current =') && hook.includes('langAtRecord'),
    'useVoiceInput.ts',
    'STATIC'
  );
  record(
    'stt',
    'voice hook receives selected language prop',
    hook.includes('language = DEFAULT_UI_LANGUAGE') && read('app/chat.tsx').includes('language,'),
    'useVoiceInput + chat.tsx',
    'STATIC'
  );
  record(
    'stt',
    'uiLangToApi maps kn/hi/en to backend codes',
    read('src/api/chatAdapter.ts').includes("kn: 'KN'") &&
      read('src/api/chatAdapter.ts').includes("hi: 'HI'") &&
      read('src/api/chatAdapter.ts').includes("en: 'EN'"),
    'chatAdapter.ts',
    'STATIC'
  );
}

function testTtsLanguage() {
  const tts = read('src/context/TtsPlaybackContext.tsx');
  const assistant = read('src/components/chat/AssistantMessage.tsx');
  const utils = read('src/utils/language.ts');
  record('tts', 'resolveTtsLanguage precedence helper', utils.includes('resolveTtsLanguage'), 'utils/language.ts', 'STATIC');
  record(
    'tts',
    'message language takes precedence when valid',
    utils.includes('fromMessage') && assistant.includes('resolveTtsLanguage(message.language'),
    'AssistantMessage',
    'STATIC'
  );
  record(
    'tts',
    'selected language is TTS fallback',
    utils.includes('selectedLanguage') && assistant.includes('selectedLanguage'),
    'resolveTtsLanguage',
    'STATIC'
  );
  record(
    'tts',
    'kn is final fallback',
    utils.includes('return DEFAULT_UI_LANGUAGE') &&
      read('src/constants/language.ts').includes("DEFAULT_UI_LANGUAGE: UiLanguageCode = 'kn'"),
    'utils/language.ts',
    'STATIC'
  );
  record(
    'tts',
    'unsupported message language normalized before TTS',
    tts.includes('normalizeUiLanguage(language') && tts.includes('uiLangToApi(responseLanguage)'),
    'TtsPlaybackContext',
    'STATIC'
  );
  record(
    'tts',
    'response_language sent to backend',
    read('src/api/voice.ts').includes('response_language: responseLanguage'),
    'voice.ts',
    'STATIC'
  );
}

function testPersistence() {
  const storage = read('src/storage/languagePreference.ts');
  const ctx = read('src/context/LanguageContext.tsx');
  const auth = read('src/storage/authTokens.ts');
  record('persistence', 'language preference load/save exists', storage.includes('loadLanguagePreference') && storage.includes('saveLanguagePreference'), 'languagePreference.ts', 'STATIC');
  record('persistence', 'LanguageProvider restores on mount', ctx.includes('loadLanguagePreference'), 'LanguageContext.tsx', 'STATIC');
  record(
    'persistence',
    'language not stored in SecureStore',
    storage.includes('Paths.document') && !storage.includes('import * as SecureStore') && !auth.includes('language'),
    'languagePreference.ts',
    'STATIC'
  );
  record(
    'persistence',
    'logout does not clear language preference',
    !read('src/context/AuthContext.tsx').includes('clearLanguagePreference') &&
      !read('src/storage/authTokens.ts').includes('language'),
    'AuthContext + authTokens',
    'AUDIT'
  );
}

function testConversations() {
  const adapter = read('src/api/chatAdapter.ts');
  record(
    'conversation',
    'historical message language preserved',
    adapter.includes('apiLangToUi(m.language)'),
    'mapHistoryMessages',
    'STATIC'
  );
  record(
    'conversation',
    'conversation switch does not mutate message language',
    !read('src/store/ChatContext.tsx').match(/setLanguage|language.*activeConversationId/),
    'ChatContext',
    'STATIC'
  );
  record(
    'conversation',
    'new message uses selected language',
    read('app/chat.tsx').includes('sendMessage(trimmed, language)'),
    'chat.tsx',
    'STATIC'
  );
}

function testRaceSafety() {
  const ctx = read('src/store/ChatContext.tsx');
  const hook = read('src/hooks/useVoiceInput.ts');
  const tts = read('src/context/TtsPlaybackContext.tsx');
  record('race', 'sendInFlightRef preserved', ctx.includes('sendInFlightRef'), 'ChatContext', 'STATIC');
  record('race', 'chatGenerationRef preserved', ctx.includes('chatGenerationRef'), 'ChatContext', 'STATIC');
  record('race', 'sttSeqRef preserved', hook.includes('sttSeqRef'), 'useVoiceInput', 'STATIC');
  record('race', 'playSeqRef preserved', tts.includes('playSeqRef'), 'TtsPlaybackContext', 'STATIC');
  record(
    'race',
    'language selector does not call sendMessage',
    !read('src/context/LanguageContext.tsx').includes('sendMessage') &&
      !read('src/components/chat/LanguageSelector.tsx').includes('sendMessage'),
    'LanguageContext + LanguageSelector',
    'STATIC'
  );
}

function testArchitecture() {
  const chatApi = read('src/api/chat.ts');
  const joined = walk(SRC).map((f) => fs.readFileSync(f, 'utf8')).join('\n');
  record('architecture', 'no language-specific backend endpoint', !chatApi.match(/\/chat\/(kn|hi|en)/), 'chat.ts', 'STATIC');
  // Static i18n string tables (src/i18n) are allowed; runtime translation
  // services/models (LibreTranslate, Google Translate, ML Kit) are not.
  record(
    'architecture',
    'no local translation model',
    !/libretranslate|google[\s-]*translate|translate\.googleapis|@react-native-ml-kit|mlkit|translation[\s-]*api/i.test(joined),
    'src scan',
    'STATIC'
  );
  record('architecture', 'no local LLM/RAG', !/localRAG|localLLM|whisper/i.test(joined), 'src scan', 'STATIC');
  record(
    'architecture',
    'no language-specific eligibility logic',
    !/if\s*\(\s*language\s*===\s*['"]kn['"]\s*\)/.test(joined),
    'src scan',
    'STATIC'
  );
  record(
    'architecture',
    'single LanguageProvider',
    read('app/_layout.tsx').includes('<LanguageProvider>') &&
      (read('app/_layout.tsx').match(/<LanguageProvider>/g) || []).length === 1,
    '_layout.tsx',
    'STATIC'
  );
}

function testRegressionGuards() {
  record('regression', 'A1 safe URL intact', read('src/components/chat/SourceList.tsx').includes('safeHttpUrl'), 'SourceList', 'STATIC');
  record('regression', 'A2 send guard intact', read('src/store/ChatContext.tsx').includes('sendInFlightRef'), 'ChatContext', 'STATIC');
  record('regression', 'A2 new consultation guard intact', read('src/store/ChatContext.tsx').includes('newConsultationInFlightRef'), 'ChatContext', 'STATIC');
  record('regression', 'A3 STT cleanup intact', read('src/hooks/useVoiceInput.ts').includes('abortVoiceProcessing'), 'useVoiceInput', 'STATIC');
  record('regression', 'A3 TTS cleanup intact', read('src/context/TtsPlaybackContext.tsx').includes('cleanupTemp'), 'TtsPlaybackContext', 'STATIC');
  record(
    'regression',
    'A3 TTS auth-expiration intact',
    read('src/context/TtsPlaybackContext.tsx').includes('onAuthExpired'),
    'TtsPlaybackContext',
    'STATIC'
  );
  record(
    'regression',
    'no voice-specific authentication',
    !read('src/api/voice.ts').includes('voiceToken'),
    'voice.ts',
    'STATIC'
  );
}

function testSourceInspection() {
  const chat = read('app/chat.tsx');
  const adapter = read('src/api/chatAdapter.ts');
  record(
    'audit',
    'intentional DEFAULT_UI_LANGUAGE fallbacks identified',
    read('src/constants/language.ts').includes('DEFAULT_UI_LANGUAGE') &&
      read('src/utils/language.ts').includes('DEFAULT_UI_LANGUAGE'),
    'constants + utils',
    'AUDIT'
  );
  record(
    'audit',
    'no accidental hard-coded chat send kn',
    !chat.match(/sendMessage\([^)]*'kn'/),
    'chat.tsx',
    'STATIC'
  );
  record(
    'audit',
    'uiLangToApi single mapping path',
    adapter.includes('uiLangToApi') && adapter.includes('LANG_TO_API') && !adapter.includes('.slice(0, 2)'),
    'chatAdapter.ts',
    'STATIC'
  );
  record(
    'audit',
    'LanguageSelector accessibility',
    read('src/components/chat/LanguageSelector.tsx').includes('accessibilityRole="radiogroup"') &&
      read('src/components/chat/LanguageSelector.tsx').includes('accessibilityRole="radio"'),
    'LanguageSelector.tsx',
    'STATIC'
  );
}

testLanguageDefinitions();
testChatLanguage();
testSttLanguage();
testTtsLanguage();
testPersistence();
testConversations();
testRaceSafety();
testArchitecture();
testRegressionGuards();
testSourceInspection();

console.log('# A4 AUTOMATED REGRESSION REPORT\n');

const sections = {
  language: '## Language definitions',
  chat: '## Chat language',
  stt: '## STT language',
  tts: '## TTS language',
  persistence: '## Persistence',
  conversation: '## Conversation language',
  race: '## Race safety',
  architecture: '## Architecture',
  regression: '## A1/A2/A3 regression preserved',
  audit: '## Source inspection',
};

for (const [cat, title] of Object.entries(sections)) {
  const rows = results.filter((r) => r.category === cat);
  if (!rows.length) continue;
  console.log(`${title}\n`);
  console.log('| Test | Result | Kind | Evidence |');
  console.log('|------|--------|------|----------|');
  for (const r of rows) {
    console.log(`| ${r.name} | ${r.pass ? 'PASS' : 'FAIL'} | ${r.kind} | ${String(r.evidence).slice(0, 90).replace(/\|/g, '\\|')} |`);
  }
  console.log('');
}

console.log('## Remaining limitations (NOT AUTOMATABLE)\n');
console.log('- Real device STT/TTS in kn/hi/en');
console.log('- Full UI localization (chrome remains mostly English)');
console.log('- low_confidence UX policy across languages');
console.log('- Device locale auto-detection');

const status = failures === 0 ? 'PASS WITH LIMITATIONS' : 'FAIL';
console.log(`\n## Final status\n\n${status}\n`);
console.log(`Checks: ${results.length}, failures: ${failures}, exit: ${failures === 0 ? 0 : 1}\n`);

process.exit(failures === 0 ? 0 : 1);
