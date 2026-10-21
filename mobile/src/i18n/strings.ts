/**
 * Lightweight UI string tables for GramSakhi Android (en / hi / kn).
 *
 * No i18n library — plain typed objects. English is the source of truth;
 * missing keys in other languages fall back to English at lookup time.
 * The product name "GramSakhi" is intentionally kept untranslated everywhere.
 */
import type { UiLanguageCode } from '../constants/language';

const en = {
  // Landing screen
  'landing.eyebrow': 'Last-mile governance',
  'landing.headline': 'Your trusted advisor for government schemes',
  'landing.lead':
    'A vernacular, voice-first assistant for reliable scheme information — grounded in verified official documents.',
  'landing.signIn': 'Sign in',
  'landing.learnMore': 'Learn more',
  'landing.retryConnection': 'Retry connection',
  'feature.voiceTitle': 'Voice-first access',
  'feature.voiceDesc': 'Ask about schemes by speaking — designed for limited digital literacy.',
  'feature.groundedTitle': 'Grounded answers',
  'feature.groundedDesc': 'Responses come from verified government documents — not guessing.',
  'feature.multilingualTitle': 'Multilingual',
  'feature.multilingualDesc': 'Kannada, Hindi, and English with official-source grounding.',
  'feature.evidenceTitle': 'Evidence-first',
  'feature.evidenceDesc': 'If reliable evidence is missing, GramSakhi says so clearly.',

  // Login screen
  'login.backToHome': 'Back to home',
  'login.title': 'Welcome back',
  'login.subtitle': 'Sign in with your mobile number',
  'login.mobileNumber': 'Mobile number',
  'login.phoneA11y': 'Mobile number, 10 digits',
  'login.phonePlaceholder': '10-digit mobile number',
  'login.sendOtp': 'Send OTP',
  'login.invalidPhone': 'Mobile number must be exactly 10 digits.',
  'login.sendOtpFailed': 'Failed to send OTP. Please try again.',

  // OTP screen
  'otp.changeNumber': 'Change number',
  'otp.signedIn': "You're signed in",
  'otp.enterCode': 'Enter verification code',
  'otp.sentTo': 'OTP sent to',
  'otp.enterOtp': 'Enter OTP',
  'otp.resend': 'Resend OTP',
  'otp.verifyContinue': 'Verify and continue',
  'otp.backToLogin': 'Back to login',
  'otp.opening': 'Opening GramSakhi…',
  'otp.invalidLength': 'OTP must be exactly 6 digits.',
  'otp.invalidCode': 'Invalid OTP code.',
  'otp.resendFailed': 'Failed to resend OTP.',
  'otp.notRegistered': 'This mobile number is verified. Create your GramSakhi account to continue.',
  'otp.displayName': 'Full name (optional)',
  'otp.displayNamePlaceholder': 'Your name',
  'otp.createAccount': 'Create account',
  'otp.registerFailed': 'Could not create your account. Please try again.',

  // Chat screen chrome
  'chat.loading': 'Loading…',
  'chat.generating': 'GramSakhi is preparing your answer…',
  'header.openConversations': 'Open conversations',
  'header.newConsultation': 'Start new consultation',
  'header.signOut': 'Sign out',
  'language.select': 'Select language',

  // Empty chat
  'empty.title': 'Ask about government schemes',
  'empty.body':
    'GramSakhi answers from verified official documents. Try asking about eligibility, documents, or how to apply.',
  'empty.hint1': 'Am I eligible for PM-KISAN?',
  'empty.hint2': 'Documents needed for Ayushman Bharat',
  'empty.hint3': 'How to apply for a farmer scheme in Karnataka',
  'empty.startA11y': 'Start a conversation',

  // Message list
  'list.loadingConversation': 'Loading conversation…',

  // Assistant message
  'badge.verified': 'Verified',
  'badge.limited': 'Limited evidence',
  'badge.partial': 'Partial evidence',
  'speak.listen': 'Listen',
  'speak.stop': 'Stop',
  'speak.playA11y': 'Play response',
  'speak.stopA11y': 'Stop response',
  'sources.title': 'Official sources',
  'meta.next': 'Next:',
  'meta.stillNeeded': 'Still needed:',
  'meta.nextSteps': 'Next steps',

  // Message composer
  'composer.voiceTranscribed': 'Voice transcribed',
  'composer.openSettings': 'Open settings',
  'composer.recording': 'Recording',
  'composer.cancel': 'Cancel',
  'composer.cancelRecordingA11y': 'Cancel recording',
  'composer.stopRecordingA11y': 'Stop recording',
  'composer.transcribingA11y': 'Transcribing voice',
  'composer.startVoiceA11y': 'Start voice input',
  'composer.sendA11y': 'Send message',
  'composer.inputA11y': 'Type your question about government schemes',
  'composer.placeholder': 'Ask about schemes, eligibility, documents…',
  'composer.transcribingPlaceholder': 'Transcribing your voice…',
  'composer.disclaimer':
    'GramSakhi uses verified government sources. Always confirm critical details officially.',

  // Conversation sheet
  'sheet.heading': 'Your consultations',
  'sheet.new': 'New consultation',
  'sheet.closeA11y': 'Close conversations',
  'sheet.loading': 'Loading conversations…',
  'sheet.emptyTitle': 'No conversations yet',
  'sheet.emptyBody': 'Start a new consultation to ask about government schemes.',

  // Error boundary
  'error.title': 'Something went wrong',
  'error.body': 'GramSakhi hit an unexpected problem. Please close and reopen the app, or try again.',
  'error.tryAgain': 'Try again',
} as const;

export type StringKey = keyof typeof en;

type StringTable = Record<StringKey, string>;

const hi: StringTable = {
  'landing.eyebrow': 'गाँव तक पहुँचती सरकारी सेवाएँ',
  'landing.headline': 'सरकारी योजनाओं के लिए आपका भरोसेमंद सलाहकार',
  'landing.lead':
    'विश्वसनीय योजना जानकारी के लिए आपकी भाषा में, आवाज़-आधारित सहायक — प्रमाणित सरकारी दस्तावेज़ों पर आधारित।',
  'landing.signIn': 'साइन इन करें',
  'landing.learnMore': 'और जानें',
  'landing.retryConnection': 'फिर से जोड़ें',
  'feature.voiceTitle': 'आवाज़ से उपयोग',
  'feature.voiceDesc': 'बोलकर योजनाओं के बारे में पूछें — कम डिजिटल जानकारी वालों के लिए बनाया गया।',
  'feature.groundedTitle': 'प्रमाणित उत्तर',
  'feature.groundedDesc': 'जवाब प्रमाणित सरकारी दस्तावेज़ों से आते हैं — अनुमान से नहीं।',
  'feature.multilingualTitle': 'बहुभाषी',
  'feature.multilingualDesc': 'कन्नड़, हिन्दी और अंग्रेज़ी — आधिकारिक स्रोतों के आधार पर।',
  'feature.evidenceTitle': 'साक्ष्य-आधारित',
  'feature.evidenceDesc': 'अगर भरोसेमंद प्रमाण नहीं मिलता, तो GramSakhi साफ़-साफ़ बता देती है।',

  'login.backToHome': 'होम पर वापस जाएँ',
  'login.title': 'फिर से स्वागत है',
  'login.subtitle': 'सरकारी योजनाओं के बारे में पूछने के लिए साइन इन करें',
  'login.mobileNumber': 'मोबाइल नंबर',
  'login.phoneA11y': 'मोबाइल नंबर, 10 अंक',
  'login.phonePlaceholder': '10 अंकों का मोबाइल नंबर',
  'login.sendOtp': 'OTP भेजें',
  'login.invalidPhone': 'मोबाइल नंबर ठीक 10 अंकों का होना चाहिए।',
  'login.sendOtpFailed': 'OTP भेजने में समस्या हुई। कृपया फिर से कोशिश करें।',

  'otp.changeNumber': 'नंबर बदलें',
  'otp.signedIn': 'आप साइन इन हो गए हैं',
  'otp.enterCode': 'सत्यापन कोड डालें',
  'otp.sentTo': 'इस नंबर पर OTP भेजा गया:',
  'otp.enterOtp': 'OTP डालें',
  'otp.resend': 'OTP दोबारा भेजें',
  'otp.verifyContinue': 'सत्यापित करें और आगे बढ़ें',
  'otp.backToLogin': 'लॉगिन पर वापस जाएँ',
  'otp.opening': 'GramSakhi खुल रही है…',
  'otp.invalidLength': 'OTP ठीक 6 अंकों का होना चाहिए।',
  'otp.invalidCode': 'OTP कोड गलत है।',
  'otp.resendFailed': 'OTP दोबारा भेजने में समस्या हुई।',
  'otp.notRegistered':
    'यह मोबाइल नंबर अभी पंजीकृत नहीं है। कृपया GramSakhi वेब ऐप से खाता बनाएँ, फिर यहाँ OTP से साइन इन करें।',
  'otp.displayName': 'पूरा नाम (वैकल्पिक)',
  'otp.displayNamePlaceholder': 'आपका नाम',
  'otp.createAccount': 'खाता बनाएँ',
  'otp.registerFailed': 'खाता नहीं बन सका। कृपया फिर से कोशिश करें।',

  'chat.loading': 'लोड हो रहा है…',
  'chat.generating': 'GramSakhi आपका जवाब तैयार कर रही है…',
  'header.openConversations': 'बातचीत खोलें',
  'header.newConsultation': 'नया परामर्श शुरू करें',
  'header.signOut': 'साइन आउट करें',
  'language.select': 'भाषा चुनें',

  'empty.title': 'सरकारी योजनाओं के बारे में पूछें',
  'empty.body':
    'GramSakhi प्रमाणित सरकारी दस्तावेज़ों से जवाब देती है। पात्रता, दस्तावेज़ों या आवेदन के बारे में पूछकर देखें।',
  'empty.hint1': 'क्या मैं PM-KISAN के लिए पात्र हूँ?',
  'empty.hint2': 'आयुष्मान भारत के लिए ज़रूरी दस्तावेज़',
  'empty.hint3': 'कर्नाटक में किसान योजना के लिए आवेदन कैसे करें',
  'empty.startA11y': 'बातचीत शुरू करें',

  'list.loadingConversation': 'बातचीत लोड हो रही है…',

  'badge.verified': 'प्रमाणित',
  'badge.limited': 'सीमित प्रमाण',
  'badge.partial': 'आंशिक प्रमाण',
  'speak.listen': 'सुनें',
  'speak.stop': 'रोकें',
  'speak.playA11y': 'जवाब सुनें',
  'speak.stopA11y': 'जवाब रोकें',
  'sources.title': 'आधिकारिक स्रोत',
  'meta.next': 'आगे:',
  'meta.stillNeeded': 'अभी ज़रूरी:',
  'meta.nextSteps': 'अगले कदम',

  'composer.voiceTranscribed': 'आवाज़ लिख ली गई',
  'composer.openSettings': 'सेटिंग्स खोलें',
  'composer.recording': 'रिकॉर्डिंग',
  'composer.cancel': 'रद्द करें',
  'composer.cancelRecordingA11y': 'रिकॉर्डिंग रद्द करें',
  'composer.stopRecordingA11y': 'रिकॉर्डिंग रोकें',
  'composer.transcribingA11y': 'आवाज़ लिखी जा रही है',
  'composer.startVoiceA11y': 'आवाज़ से बोलना शुरू करें',
  'composer.sendA11y': 'संदेश भेजें',
  'composer.inputA11y': 'सरकारी योजनाओं के बारे में अपना सवाल लिखें',
  'composer.placeholder': 'योजनाओं, पात्रता, दस्तावेज़ों के बारे में पूछें…',
  'composer.transcribingPlaceholder': 'आपकी आवाज़ लिखी जा रही है…',
  'composer.disclaimer':
    'GramSakhi प्रमाणित सरकारी स्रोतों का उपयोग करती है। महत्वपूर्ण जानकारी की आधिकारिक पुष्टि ज़रूर करें।',

  'sheet.heading': 'आपके परामर्श',
  'sheet.new': 'नया परामर्श',
  'sheet.closeA11y': 'बातचीत सूची बंद करें',
  'sheet.loading': 'बातचीत लोड हो रही है…',
  'sheet.emptyTitle': 'अभी कोई बातचीत नहीं',
  'sheet.emptyBody': 'सरकारी योजनाओं के बारे में पूछने के लिए नया परामर्श शुरू करें।',

  'error.title': 'कुछ गड़बड़ हो गई',
  'error.body':
    'GramSakhi में एक अनपेक्षित समस्या आई। कृपया ऐप बंद करके दोबारा खोलें, या फिर से कोशिश करें।',
  'error.tryAgain': 'फिर से कोशिश करें',
};

const kn: StringTable = {
  'landing.eyebrow': 'ಹಳ್ಳಿಯವರೆಗೂ ತಲುಪುವ ಸರ್ಕಾರಿ ಸೇವೆಗಳು',
  'landing.headline': 'ಸರ್ಕಾರಿ ಯೋಜನೆಗಳಿಗೆ ನಿಮ್ಮ ವಿಶ್ವಾಸಾರ್ಹ ಸಲಹೆಗಾರ',
  'landing.lead':
    'ವಿಶ್ವಾಸಾರ್ಹ ಯೋಜನಾ ಮಾಹಿತಿಗಾಗಿ ನಿಮ್ಮ ಭಾಷೆಯಲ್ಲಿ, ಧ್ವನಿ-ಆಧಾರಿತ ಸಹಾಯಕ — ಪರಿಶೀಲಿತ ಅಧಿಕೃತ ದಾಖಲೆಗಳ ಆಧಾರದಲ್ಲಿ.',
  'landing.signIn': 'ಸೈನ್ ಇನ್ ಮಾಡಿ',
  'landing.learnMore': 'ಇನ್ನಷ್ಟು ತಿಳಿಯಿರಿ',
  'landing.retryConnection': 'ಮತ್ತೆ ಸಂಪರ್ಕಿಸಿ',
  'feature.voiceTitle': 'ಧ್ವನಿ ಮೂಲಕ ಬಳಕೆ',
  'feature.voiceDesc': 'ಮಾತನಾಡಿ ಯೋಜನೆಗಳ ಬಗ್ಗೆ ಕೇಳಿ — ಕಡಿಮೆ ಡಿಜಿಟಲ್ ಪರಿಚಯವಿರುವವರಿಗಾಗಿ ರೂಪಿಸಲಾಗಿದೆ.',
  'feature.groundedTitle': 'ಆಧಾರಸಹಿತ ಉತ್ತರಗಳು',
  'feature.groundedDesc': 'ಉತ್ತರಗಳು ಪರಿಶೀಲಿತ ಸರ್ಕಾರಿ ದಾಖಲೆಗಳಿಂದ ಬರುತ್ತವೆ — ಊಹೆಯಿಂದ ಅಲ್ಲ.',
  'feature.multilingualTitle': 'ಬಹುಭಾಷಾ ಬೆಂಬಲ',
  'feature.multilingualDesc': 'ಕನ್ನಡ, ಹಿಂದಿ ಮತ್ತು ಇಂಗ್ಲಿಷ್ — ಅಧಿಕೃತ ಮೂಲಗಳ ಆಧಾರದೊಂದಿಗೆ.',
  'feature.evidenceTitle': 'ಸಾಕ್ಷ್ಯ-ಆಧಾರಿತ',
  'feature.evidenceDesc': 'ವಿಶ್ವಾಸಾರ್ಹ ಪುರಾವೆ ಇಲ್ಲದಿದ್ದರೆ, GramSakhi ಅದನ್ನು ಸ್ಪಷ್ಟವಾಗಿ ತಿಳಿಸುತ್ತದೆ.',

  'login.backToHome': 'ಮುಖಪುಟಕ್ಕೆ ಹಿಂತಿರುಗಿ',
  'login.title': 'ಮತ್ತೆ ಸ್ವಾಗತ',
  'login.subtitle': 'ಸರ್ಕಾರಿ ಯೋಜನೆಗಳ ಬಗ್ಗೆ ಕೇಳಲು ಸೈನ್ ಇನ್ ಮಾಡಿ',
  'login.mobileNumber': 'ಮೊಬೈಲ್ ಸಂಖ್ಯೆ',
  'login.phoneA11y': 'ಮೊಬೈಲ್ ಸಂಖ್ಯೆ, 10 ಅಂಕಿಗಳು',
  'login.phonePlaceholder': '10 ಅಂಕಿಯ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ',
  'login.sendOtp': 'OTP ಕಳುಹಿಸಿ',
  'login.invalidPhone': 'ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ನಿಖರವಾಗಿ 10 ಅಂಕಿಗಳಾಗಿರಬೇಕು.',
  'login.sendOtpFailed': 'OTP ಕಳುಹಿಸಲು ಆಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',

  'otp.changeNumber': 'ಸಂಖ್ಯೆ ಬದಲಿಸಿ',
  'otp.signedIn': 'ನೀವು ಸೈನ್ ಇನ್ ಆಗಿದ್ದೀರಿ',
  'otp.enterCode': 'ಪರಿಶೀಲನಾ ಕೋಡ್ ನಮೂದಿಸಿ',
  'otp.sentTo': 'ಈ ಸಂಖ್ಯೆಗೆ OTP ಕಳುಹಿಸಲಾಗಿದೆ:',
  'otp.enterOtp': 'OTP ನಮೂದಿಸಿ',
  'otp.resend': 'OTP ಮತ್ತೆ ಕಳುಹಿಸಿ',
  'otp.verifyContinue': 'ಪರಿಶೀಲಿಸಿ ಮುಂದುವರಿಯಿರಿ',
  'otp.backToLogin': 'ಲಾಗಿನ್‌ಗೆ ಹಿಂತಿರುಗಿ',
  'otp.opening': 'GramSakhi ತೆರೆಯುತ್ತಿದೆ…',
  'otp.invalidLength': 'OTP ನಿಖರವಾಗಿ 6 ಅಂಕಿಗಳಾಗಿರಬೇಕು.',
  'otp.invalidCode': 'OTP ಕೋಡ್ ತಪ್ಪಾಗಿದೆ.',
  'otp.resendFailed': 'OTP ಮತ್ತೆ ಕಳುಹಿಸಲು ಆಗಲಿಲ್ಲ.',
  'otp.notRegistered':
    'ಈ ಮೊಬೈಲ್ ಸಂಖ್ಯೆ ಇನ್ನೂ ನೋಂದಣಿಯಾಗಿಲ್ಲ. ದಯವಿಟ್ಟು GramSakhi ವೆಬ್ ಆ್ಯಪ್ ಬಳಸಿ ಖಾತೆ ರಚಿಸಿ, ನಂತರ ಇಲ್ಲಿ OTP ಮೂಲಕ ಸೈನ್ ಇನ್ ಮಾಡಿ.',
  'otp.displayName': 'ಪೂರ್ಣ ಹೆಸರು (ಐಚ್ಛಿಕ)',
  'otp.displayNamePlaceholder': 'ನಿಮ್ಮ ಹೆಸರು',
  'otp.createAccount': 'ಖಾತೆ ರಚಿಸಿ',
  'otp.registerFailed': 'ಖಾತೆ ರಚಿಸಲು ಆಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',

  'chat.loading': 'ಲೋಡ್ ಆಗುತ್ತಿದೆ…',
  'chat.generating': 'GramSakhi ನಿಮ್ಮ ಉತ್ತರವನ್ನು ಸಿದ್ಧಪಡಿಸುತ್ತಿದೆ…',
  'header.openConversations': 'ಸಂಭಾಷಣೆಗಳನ್ನು ತೆರೆಯಿರಿ',
  'header.newConsultation': 'ಹೊಸ ಸಮಾಲೋಚನೆ ಪ್ರಾರಂಭಿಸಿ',
  'header.signOut': 'ಸೈನ್ ಔಟ್ ಮಾಡಿ',
  'language.select': 'ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ',

  'empty.title': 'ಸರ್ಕಾರಿ ಯೋಜನೆಗಳ ಬಗ್ಗೆ ಕೇಳಿ',
  'empty.body':
    'GramSakhi ಪರಿಶೀಲಿತ ಅಧಿಕೃತ ದಾಖಲೆಗಳಿಂದ ಉತ್ತರಿಸುತ್ತದೆ. ಅರ್ಹತೆ, ದಾಖಲೆಗಳು ಅಥವಾ ಅರ್ಜಿ ಸಲ್ಲಿಸುವ ಬಗ್ಗೆ ಕೇಳಿ ನೋಡಿ.',
  'empty.hint1': 'ನಾನು PM-KISAN ಗೆ ಅರ್ಹನೇ?',
  'empty.hint2': 'ಆಯುಷ್ಮಾನ್ ಭಾರತ್‌ಗೆ ಬೇಕಾದ ದಾಖಲೆಗಳು',
  'empty.hint3': 'ಕರ್ನಾಟಕದಲ್ಲಿ ರೈತ ಯೋಜನೆಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸುವುದು ಹೇಗೆ',
  'empty.startA11y': 'ಸಂಭಾಷಣೆ ಪ್ರಾರಂಭಿಸಿ',

  'list.loadingConversation': 'ಸಂಭಾಷಣೆ ಲೋಡ್ ಆಗುತ್ತಿದೆ…',

  'badge.verified': 'ಪರಿಶೀಲಿತ',
  'badge.limited': 'ಸೀಮಿತ ಪುರಾವೆ',
  'badge.partial': 'ಭಾಗಶಃ ಪುರಾವೆ',
  'speak.listen': 'ಕೇಳಿ',
  'speak.stop': 'ನಿಲ್ಲಿಸಿ',
  'speak.playA11y': 'ಉತ್ತರವನ್ನು ಕೇಳಿ',
  'speak.stopA11y': 'ಉತ್ತರವನ್ನು ನಿಲ್ಲಿಸಿ',
  'sources.title': 'ಅಧಿಕೃತ ಮೂಲಗಳು',
  'meta.next': 'ಮುಂದೆ:',
  'meta.stillNeeded': 'ಇನ್ನೂ ಬೇಕಾಗಿರುವುದು:',
  'meta.nextSteps': 'ಮುಂದಿನ ಹಂತಗಳು',

  'composer.voiceTranscribed': 'ಧ್ವನಿ ಬರಹವಾಗಿ ಪರಿವರ್ತನೆಯಾಗಿದೆ',
  'composer.openSettings': 'ಸೆಟ್ಟಿಂಗ್ಸ್ ತೆರೆಯಿರಿ',
  'composer.recording': 'ರೆಕಾರ್ಡಿಂಗ್',
  'composer.cancel': 'ರದ್ದುಮಾಡಿ',
  'composer.cancelRecordingA11y': 'ರೆಕಾರ್ಡಿಂಗ್ ರದ್ದುಮಾಡಿ',
  'composer.stopRecordingA11y': 'ರೆಕಾರ್ಡಿಂಗ್ ನಿಲ್ಲಿಸಿ',
  'composer.transcribingA11y': 'ಧ್ವನಿ ಬರಹಕ್ಕೆ ಪರಿವರ್ತನೆಯಾಗುತ್ತಿದೆ',
  'composer.startVoiceA11y': 'ಧ್ವನಿ ಇನ್‌ಪುಟ್ ಪ್ರಾರಂಭಿಸಿ',
  'composer.sendA11y': 'ಸಂದೇಶ ಕಳುಹಿಸಿ',
  'composer.inputA11y': 'ಸರ್ಕಾರಿ ಯೋಜನೆಗಳ ಬಗ್ಗೆ ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಬರೆಯಿರಿ',
  'composer.placeholder': 'ಯೋಜನೆಗಳು, ಅರ್ಹತೆ, ದಾಖಲೆಗಳ ಬಗ್ಗೆ ಕೇಳಿ…',
  'composer.transcribingPlaceholder': 'ನಿಮ್ಮ ಧ್ವನಿಯನ್ನು ಬರಹಕ್ಕೆ ಪರಿವರ್ತಿಸಲಾಗುತ್ತಿದೆ…',
  'composer.disclaimer':
    'GramSakhi ಪರಿಶೀಲಿತ ಸರ್ಕಾರಿ ಮೂಲಗಳನ್ನು ಬಳಸುತ್ತದೆ. ಮುಖ್ಯ ವಿವರಗಳನ್ನು ಅಧಿಕೃತವಾಗಿ ಖಚಿತಪಡಿಸಿಕೊಳ್ಳಿ.',

  'sheet.heading': 'ನಿಮ್ಮ ಸಮಾಲೋಚನೆಗಳು',
  'sheet.new': 'ಹೊಸ ಸಮಾಲೋಚನೆ',
  'sheet.closeA11y': 'ಸಂಭಾಷಣೆ ಪಟ್ಟಿ ಮುಚ್ಚಿ',
  'sheet.loading': 'ಸಂಭಾಷಣೆಗಳು ಲೋಡ್ ಆಗುತ್ತಿವೆ…',
  'sheet.emptyTitle': 'ಇನ್ನೂ ಯಾವುದೇ ಸಂಭಾಷಣೆಗಳಿಲ್ಲ',
  'sheet.emptyBody': 'ಸರ್ಕಾರಿ ಯೋಜನೆಗಳ ಬಗ್ಗೆ ಕೇಳಲು ಹೊಸ ಸಮಾಲೋಚನೆ ಪ್ರಾರಂಭಿಸಿ.',

  'error.title': 'ಏನೋ ತಪ್ಪಾಗಿದೆ',
  'error.body':
    'GramSakhi ನಲ್ಲಿ ಅನಿರೀಕ್ಷಿತ ಸಮಸ್ಯೆ ಉಂಟಾಗಿದೆ. ದಯವಿಟ್ಟು ಆ್ಯಪ್ ಮುಚ್ಚಿ ಮತ್ತೆ ತೆರೆಯಿರಿ, ಅಥವಾ ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.',
  'error.tryAgain': 'ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ',
};

const TABLES: Record<UiLanguageCode, StringTable> = { en, hi, kn };

export type Translator = (key: StringKey) => string;

/** Build a `t(key)` lookup for a language, falling back to English. */
export function createTranslator(language: UiLanguageCode): Translator {
  const table = TABLES[language] ?? en;
  return (key) => table[key] ?? en[key];
}

export const ENGLISH_TRANSLATOR: Translator = createTranslator('en');
