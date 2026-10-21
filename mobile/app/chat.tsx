import { useRouter } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { AppState, KeyboardAvoidingView, Platform, StyleSheet, View } from 'react-native';
import { ChatHeader } from '../src/components/chat/ChatHeader';
import { MessageComposer } from '../src/components/chat/MessageComposer';
import { MessageList } from '../src/components/chat/MessageList';
import { ConversationSheet } from '../src/components/conversation/ConversationSheet';
import { TtsPlaybackProvider, useTtsPlayback } from '../src/context/TtsPlaybackContext';
import { useLanguage } from '../src/context/LanguageContext';
import { AuthLoadingGate, useRequireAuth } from '../src/hooks/useRequireAuth';
import { useAuth } from '../src/context/AuthContext';
import { useChat } from '../src/store/ChatContext';
import { useVoiceInput } from '../src/hooks/useVoiceInput';
import { colors } from '../src/theme';

function ChatScreenBody() {
  const router = useRouter();
  const { logout, status } = useAuth();
  const { language, t } = useLanguage();
  const { stopPlayback } = useTtsPlayback();
  const {
    conversations,
    loadingConversations,
    activeConversationId,
    messages,
    loadingMessages,
    isGenerating,
    error,
    initialized,
    bootstrapChat,
    fetchConversations,
    selectConversation,
    newConsultation,
    sendMessage,
    getChatGeneration,
    handleAuthFailure,
  } = useChat();

  const [sheetOpen, setSheetOpen] = useState(false);
  const [creatingConsultation, setCreatingConsultation] = useState(false);
  const [composerText, setComposerText] = useState('');

  const voice = useVoiceInput({
    language,
    disabled: !initialized || loadingMessages || isGenerating,
    getChatGeneration,
    onAuthExpired: handleAuthFailure,
    onTranscribed: async (text) => {
      setComposerText(text);
    },
    onLowConfidence: (text) => {
      setComposerText(text);
    },
  });

  const stopVoiceActivity = () => {
    stopPlayback();
    if (voice.isRecording || voice.isProcessing) {
      void voice.abortVoiceProcessing();
    }
  };

  useEffect(() => {
    void bootstrapChat();
  }, [bootstrapChat]);

  useEffect(() => {
    stopVoiceActivity();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- conversation switch only
  }, [activeConversationId]);

  useEffect(() => {
    if (status === 'unauthenticated') {
      stopVoiceActivity();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- auth transition only
  }, [status]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      if (next !== 'active') {
        stopVoiceActivity();
      }
    });
    return () => sub.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only app state hook
  }, []);

  const activeTitle = useMemo(() => {
    const active = conversations.find((c) => String(c.id) === String(activeConversationId));
    return active?.title || 'GramSakhi';
  }, [conversations, activeConversationId]);

  const handleSignOut = async () => {
    stopVoiceActivity();
    await logout();
    router.replace('/login');
  };

  const handleOpenConversations = () => {
    void fetchConversations();
    setSheetOpen(true);
  };

  const handleNewConsultation = async () => {
    stopVoiceActivity();
    setCreatingConsultation(true);
    try {
      await newConsultation();
    } finally {
      setCreatingConsultation(false);
    }
  };

  const handleSendText = () => {
    const trimmed = composerText.trim();
    if (!trimmed) return;
    void sendMessage(trimmed, language);
    setComposerText('');
  };

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={Platform.OS === 'ios' ? 0 : 0}
    >
      <View style={styles.flex}>
        <ChatHeader
          title={initialized ? activeTitle : t('chat.loading')}
          onOpenConversations={handleOpenConversations}
          onNewConsultation={() => void handleNewConsultation()}
          onSignOut={() => void handleSignOut()}
          creatingConsultation={creatingConsultation}
        />

        <MessageList
          messages={messages}
          loadingMessages={loadingMessages || !initialized}
          isGenerating={isGenerating}
          error={error}
        />

        <MessageComposer
          text={composerText}
          onChangeText={setComposerText}
          onSend={handleSendText}
          disabled={!initialized || loadingMessages}
          isGenerating={isGenerating}
          voicePhase={voice.phase}
          voiceError={voice.error}
          voicePreview={voice.previewText}
          isVoiceProcessing={voice.isProcessing}
          isRecording={voice.isRecording}
          recordingDurationMillis={voice.durationMillis}
          onVoicePress={() => void voice.startRecording()}
          onVoiceStop={() => void voice.finishRecording()}
          onVoiceCancel={() => void voice.cancelRecording()}
          onOpenVoiceSettings={voice.openSettings}
        />
      </View>

      <ConversationSheet
        visible={sheetOpen}
        onClose={() => setSheetOpen(false)}
        conversations={conversations}
        activeConversationId={activeConversationId}
        loading={loadingConversations}
        onSelect={selectConversation}
        onNewConsultation={() => void handleNewConsultation()}
      />
    </KeyboardAvoidingView>
  );
}

function ChatScreenInner() {
  const { handleAuthFailure } = useChat();

  return (
    <TtsPlaybackProvider onAuthExpired={handleAuthFailure}>
      <ChatScreenBody />
    </TtsPlaybackProvider>
  );
}

export default function ChatScreen() {
  useRequireAuth('/login');

  return (
    <AuthLoadingGate>
      <ChatScreenInner />
    </AuthLoadingGate>
  );
}

const styles = StyleSheet.create({
  flex: {
    flex: 1,
    backgroundColor: colors.background,
  },
});
