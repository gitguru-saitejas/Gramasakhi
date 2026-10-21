#!/usr/bin/env node
/**
 * A3 Android Voice / STT / TTS — automated regression verification.
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

function extractUseCallback(src, name) {
  const marker = `const ${name} = useCallback`;
  const start = src.indexOf(marker);
  if (start < 0) return '';
  const slice = src.slice(start);
  const end = slice.search(/\n  \}, \[/);
  return end >= 0 ? slice.slice(0, end) : slice;
}

// ========== Voice checks ==========
function testRecordingLifecycle() {
  const hook = read('src/hooks/useVoiceInput.ts');
  record('stt', 'busyRef recording guard', /busyRef\.current/.test(hook), 'useVoiceInput.ts', 'STATIC');
  record(
    'stt',
    'duplicate recording prevented',
    hook.includes('busyRef.current') && hook.includes("phase === 'recording'"),
    'startRecording guards',
    'STATIC'
  );
  record('stt', 'abortVoiceProcessing exists', hook.includes('abortVoiceProcessing'), 'useVoiceInput.ts', 'STATIC');
  record(
    'stt',
    'abort increments sttSeqRef',
    /abortVoiceProcessing[\s\S]*sttSeqRef\.current \+= 1/.test(hook),
    'invalidates in-flight STT',
    'STATIC'
  );
  record(
    'stt',
    'STT finally deletes temp audio',
    extractUseCallback(hook, 'finishRecording').includes('deleteTempAudio(fileUri)') &&
      extractUseCallback(hook, 'finishRecording').includes('finally'),
    'finishRecording finally',
    'STATIC'
  );
  record(
    'stt',
    'sttSeqRef stale guard',
    hook.includes('sttSeq !== sttSeqRef.current') && hook.includes('genAtRecord !== getChatGeneration()'),
    'useVoiceInput.ts',
    'STATIC'
  );
  record(
    'stt',
    'unmount cleanup',
    hook.includes('return () =>') && hook.includes('sttSeqRef.current += 1'),
    'useEffect cleanup',
    'STATIC'
  );
}

function testSttApi() {
  const voice = read('src/api/voice.ts');
  record('stt', 'multipart field audio', voice.includes("form.append('audio'"), 'voice.ts', 'STATIC');
  record('stt', 'optional language_hint', voice.includes("form.append('language_hint'"), 'voice.ts', 'STATIC');
  record('stt', 'STT Authorization header', voice.includes('Authorization: `Bearer ${token}`'), 'voice.ts', 'STATIC');
  record('stt', 'STT no retry', !voice.includes('retry'), 'voice.ts', 'STATIC');
  record(
    'stt',
    'malformed STT response rejected',
    voice.includes("typeof data !== 'object'"),
    'transcribeAudio',
    'STATIC'
  );
  record(
    'stt',
    'STT timeout configured',
    read('src/constants/voice.ts').includes('STT_REQUEST_TIMEOUT_MS = 120_000'),
    '120s',
    'STATIC'
  );
  record(
    'stt',
    'STT error mapping exists',
    read('src/utils/voiceErrors.ts').includes('mapTranscribeFailure') &&
      read('src/utils/voiceErrors.ts').includes('friendlyVoiceError'),
    'voiceErrors.ts',
    'STATIC'
  );
  record(
    'stt',
    'STT 401 uses auth failure path',
    read('src/hooks/useVoiceInput.ts').includes('isAuthError(err)') &&
      read('src/hooks/useVoiceInput.ts').includes('onAuthExpired()'),
    'useVoiceInput',
    'STATIC'
  );
}

function testTts() {
  const tts = read('src/context/TtsPlaybackContext.tsx');
  const voice = read('src/api/voice.ts');
  record('tts', 'playSeqRef guard', tts.includes('playSeqRef') && tts.includes('seq !== playSeqRef.current'), 'TtsPlaybackContext', 'STATIC');
  record(
    'tts',
    'stopPlayback invalidates pending synthesis',
    /stopPlayback[\s\S]*playSeqRef\.current \+= 1/.test(tts),
    'TtsPlaybackContext',
    'STATIC'
  );
  record('tts', 'TTS uses response_language', voice.includes('response_language: responseLanguage'), 'voice.ts', 'STATIC');
  record('tts', 'TTS no retry', !voice.match(/synthesizeSpeech[\s\S]*retry/), 'voice.ts', 'STATIC');
  record('tts', 'TTS cleanup on finish', tts.includes('status.didJustFinish') && tts.includes('stopPlayback'), 'TtsPlaybackContext', 'STATIC');
  record('tts', 'TTS cleanup on stop', tts.includes('cleanupTemp'), 'TtsPlaybackContext', 'STATIC');
  record('tts', 'TTS cleanup on replace stale synth', tts.includes('await deleteTempAudio(uri)'), 'TtsPlaybackContext', 'STATIC');
  record('tts', 'TTS unmount cleanup', tts.includes('useEffect(() => () =>') && tts.includes('stopPlayback()'), 'TtsPlaybackContext', 'STATIC');
  record(
    'tts',
    'TTS 401 uses onAuthExpired',
    tts.includes('onAuthExpired') && tts.includes('isAuthError(err)'),
    'TtsPlaybackContext',
    'STATIC'
  );
  record(
    'tts',
    'single playback enforced',
    tts.includes('stopPlayback();') && tts.includes('player.replace(uri)'),
    'stop before new play',
    'STATIC'
  );
}

function testChatIntegration() {
  const chat = read('app/chat.tsx');
  const ctx = read('src/store/ChatContext.tsx');
  const hook = read('src/hooks/useVoiceInput.ts');
  record(
    'integration',
    'voice uses handleAuthFailure for STT',
    hook.includes('onAuthExpired') && chat.includes('onAuthExpired: handleAuthFailure'),
    'chat + useVoiceInput',
    'STATIC'
  );
  record(
    'integration',
    'TtsPlaybackProvider wired to handleAuthFailure',
    chat.includes('<TtsPlaybackProvider onAuthExpired={handleAuthFailure}'),
    'chat.tsx',
    'STATIC'
  );
  record(
    'integration',
    'conversation switch aborts voice activity',
    chat.includes('stopVoiceActivity') && chat.includes('[activeConversationId]'),
    'chat.tsx',
    'STATIC'
  );
  record(
    'integration',
    'logout aborts voice activity',
    chat.includes("status === 'unauthenticated'") && chat.includes('stopVoiceActivity'),
    'chat.tsx',
    'STATIC'
  );
  record(
    'integration',
    'STT aborts during isProcessing on switch',
    chat.includes('voice.isProcessing') && chat.includes('abortVoiceProcessing'),
    'chat.tsx',
    'STATIC'
  );
  record(
    'integration',
    'voice transcript reaches composer then sendMessage',
    chat.includes('onTranscribed') &&
      chat.includes('setComposerText') &&
      chat.includes('sendMessage(trimmed, language)'),
    'chat.tsx voice → composer → send',
    'STATIC'
  );
  record(
    'integration',
    'A2 sendInFlightRef preserved',
    ctx.includes('sendInFlightRef'),
    'ChatContext.tsx',
    'STATIC'
  );
  record(
    'integration',
    'A2 chatGenerationRef preserved',
    ctx.includes('chatGenerationRef'),
    'ChatContext.tsx',
    'STATIC'
  );
  record(
    'integration',
    'background invalidates voice',
    chat.includes('AppState.addEventListener') && chat.includes('stopVoiceActivity'),
    'chat.tsx',
    'STATIC'
  );
  record(
    'integration',
    'voice uses shared chat JWT',
    read('src/api/voice.ts').includes('getAccessToken') && !read('src/api/voice.ts').includes('voiceToken'),
    'voice.ts',
    'STATIC'
  );
  record(
    'integration',
    'voice posts to /api/chat only',
    read('src/api/chat.ts').includes('/chat') && !read('src/api/chat.ts').includes('/voice/chat'),
    'chat.ts',
    'STATIC'
  );
  record('integration', 'no local STT/TTS/RAG', !walk(SRC).some((f) => {
    const c = fs.readFileSync(f, 'utf8');
    return /localRAG|whisper|localLLM|fakeTranscri/i.test(c);
  }), 'src scan', 'STATIC');
}

function testPrivacyAndConfig() {
  const voiceFiles = walk(SRC).filter((f) =>
    /voice|Voice|tts|Tts|audio|Audio/.test(f) || f.includes('useVoiceInput')
  );
  const joined = voiceFiles.map((f) => fs.readFileSync(f, 'utf8')).join('\n');
  record(
    'privacy',
    'no sensitive voice logging',
    !/console\.(log|warn|error)\([^)]*(transcript|audio|Bearer|Authorization)/i.test(joined),
    `${voiceFiles.length} voice-related files`,
    'STATIC'
  );
  record(
    'privacy',
    'TTS temp filenames non-PII',
    read('src/api/voice.ts').includes('gramsakhi-tts-${Date.now()}.mp3'),
    'voice.ts',
    'STATIC'
  );
  record(
    'privacy',
    'no audio URL exposed in composer UI',
    !read('src/components/chat/MessageComposer.tsx').match(/file:\/\//) &&
      !read('src/components/chat/MessageComposer.tsx').includes('recording.uri'),
    'MessageComposer.tsx',
    'STATIC'
  );
  record(
    'security',
    'A1 safe URL intact',
    read('src/components/chat/SourceList.tsx').includes('safeHttpUrl'),
    'SourceList.tsx',
    'STATIC'
  );
  record(
    'config',
    'microphone via expo-audio only',
    read('app.config.ts').includes('expo-audio') && read('app.config.ts').includes('microphonePermission'),
    'app.config.ts',
    'STATIC'
  );
}

function testLanguageAudit() {
  const hook = read('src/hooks/useVoiceInput.ts');
  const chat = read('app/chat.tsx');
  const tts = read('src/context/TtsPlaybackContext.tsx');
  const adapter = read('src/api/chatAdapter.ts');
  record('language', 'chat uses selected language for send', chat.includes('sendMessage(trimmed, language)'), 'chat.tsx', 'AUDIT');
  record('language', 'voice uses language prop from selector', chat.includes('language,') && hook.includes('languageAtRecordRef'), 'chat + useVoiceInput', 'AUDIT');
  record('language', 'TTS uses resolveTtsLanguage', read('src/components/chat/AssistantMessage.tsx').includes('resolveTtsLanguage'), 'AssistantMessage', 'AUDIT');
  record('language', 'uiLangToApi supports kn/hi/en', adapter.includes("'kn'") && adapter.includes("'hi'") && adapter.includes("'en'"), 'chatAdapter.ts', 'AUDIT');
}

testRecordingLifecycle();
testSttApi();
testTts();
testChatIntegration();
testPrivacyAndConfig();
testLanguageAudit();

console.log('# A3 AUTOMATED REGRESSION REPORT\n');

const sections = {
  stt: '## STT tests',
  tts: '## TTS tests',
  integration: '## Integration tests',
  privacy: '## Privacy tests',
  security: '## Security (A1 preserved)',
  config: '## Configuration tests',
  language: '## Language audit (A4 prep — not implemented)',
};

for (const [cat, title] of Object.entries(sections)) {
  const rows = results.filter((r) => r.category === cat);
  if (!rows.length) continue;
  console.log(title + '\n');
  console.log('| Test | Result | Kind | Evidence |');
  console.log('|------|--------|------|----------|');
  for (const r of rows) {
    console.log(`| ${r.name} | ${r.pass ? 'PASS' : 'FAIL'} | ${r.kind} | ${String(r.evidence).slice(0, 90).replace(/\|/g, '\\|')} |`);
  }
  console.log('');
}

console.log('\n## Remaining limitations (NOT AUTOMATABLE)\n');
console.log('- Native microphone permission grant/deny flow');
console.log('- Real audio record/playback on device');
console.log('- Background STT/TTS during app suspend');
console.log('- low_confidence UX (backend returns success; no mobile policy added)');

const status = failures === 0 ? 'PASS WITH LIMITATIONS' : 'FAIL';
console.log(`\n## Final status\n\n${status}\n`);
console.log(`Checks: ${results.length}, failures: ${failures}, exit: ${failures === 0 ? 0 : 1}\n`);

process.exit(failures === 0 ? 0 : 1);
