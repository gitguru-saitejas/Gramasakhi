import { useRouter } from 'expo-router';

import { useMemo, useState } from 'react';

import {

  KeyboardAvoidingView,

  Platform,

  Pressable,

  StyleSheet,

  Text,

  TextInput,

  View,

} from 'react-native';

import { GramSakhiLogo } from '../src/components/GramSakhiLogo';

import { PrimaryButton } from '../src/components/PrimaryButton';

import { ScreenContainer } from '../src/components/ScreenContainer';

import { useAuth } from '../src/context/AuthContext';

import { useLanguage } from '../src/context/LanguageContext';

import { setOtpFlowPhone } from '../src/utils/otpFlowPhone';

import { ApiClientError } from '../src/utils/errors';

import { friendlyErrorMessage } from '../src/utils/errors';

import { colors, radii, spacing, touchTargetMin, typography } from '../src/theme';



function sanitizePhone(value: string): string {

  return value.replace(/\D/g, '').slice(0, 10);

}



export default function LoginScreen() {

  const router = useRouter();

  const { requestOtp } = useAuth();

  const { t } = useLanguage();

  const [phone, setPhone] = useState('');

  const [error, setError] = useState<string | null>(null);

  const [sending, setSending] = useState(false);



  const isValid = useMemo(() => phone.length === 10, [phone]);

  const handleSendOtp = async () => {

    if (!isValid || sending) {

      if (!isValid) setError(t('login.invalidPhone'));

      return;

    }

    setSending(true);

    setError(null);

    try {

      await requestOtp(phone);

      setOtpFlowPhone(phone);

      router.push('/otp');

    } catch (err) {

      setError(

        err instanceof ApiClientError

          ? err.message

          : friendlyErrorMessage(err, t('login.sendOtpFailed'))

      );

    } finally {

      setSending(false);

    }

  };

  return (

    <ScreenContainer scroll={false}>

      <KeyboardAvoidingView

        behavior={Platform.OS === 'ios' ? 'padding' : undefined}

        style={styles.flex}

      >

        <Pressable

          accessibilityRole="button"

          accessibilityLabel={t('login.backToHome')}

          onPress={() => router.back()}

          style={styles.backLink}

        >

          <Text style={styles.backText}>← {t('login.backToHome')}</Text>

        </Pressable>



        <View style={styles.header}>

          <GramSakhiLogo size="md" />

          <Text style={styles.title} accessibilityRole="header">

            {t('login.title')}

          </Text>

          <Text style={styles.subtitle}>{t('login.subtitle')}</Text>

        </View>



        <View style={styles.card}>

          <Text style={styles.inputLabel} nativeID="phoneLabel">

            {t('login.mobileNumber')}

          </Text>

          <View style={[styles.inputRow, error ? styles.inputRowError : null]}>

            <Text style={styles.prefix} accessibilityLabel="India country code">

              +91

            </Text>

            <TextInput

              accessibilityLabel={t('login.phoneA11y')}

              autoComplete="tel"

              keyboardType="number-pad"

              maxLength={10}

              placeholder={t('login.phonePlaceholder')}

              placeholderTextColor={colors.outline}

              value={phone}

              editable={!sending}

              onChangeText={(text) => {

                setPhone(sanitizePhone(text));

                if (error) setError(null);

              }}

              style={styles.input}

              returnKeyType="done"

              onSubmitEditing={() => void handleSendOtp()}

            />

          </View>

          {error ? (

            <Text style={styles.errorText} accessibilityRole="alert">

              {error}

            </Text>

          ) : null}



          <PrimaryButton

            label={t('login.sendOtp')}

            onPress={() => void handleSendOtp()}

            disabled={!isValid}

            loading={sending}

            buttonStyle={styles.submit}

          />

        </View>

      </KeyboardAvoidingView>

    </ScreenContainer>

  );

}



const styles = StyleSheet.create({

  flex: { flex: 1 },

  backLink: {

    minHeight: touchTargetMin,

    justifyContent: 'center',

    marginTop: spacing.sm,

  },

  backText: {

    ...typography.caption,

    color: colors.secondary,

    fontWeight: '700',

  },

  header: {

    alignItems: 'center',

    marginTop: spacing.md,

    marginBottom: spacing.lg,

    gap: spacing.sm,

  },

  title: {

    ...typography.title,

    textAlign: 'center',

  },

  subtitle: {

    ...typography.body,

    textAlign: 'center',

  },

  card: {

    backgroundColor: colors.surfaceContainerLowest,

    borderRadius: radii.xl,

    padding: spacing.lg,

    borderWidth: 1,

    borderColor: colors.surfaceVariant,

    shadowColor: colors.primary,

    shadowOpacity: 0.08,

    shadowRadius: 16,

    shadowOffset: { width: 0, height: 8 },

    elevation: 4,

  },

  inputLabel: {

    ...typography.label,

    marginBottom: spacing.sm,

    color: colors.onSurfaceVariant,

  },

  inputRow: {

    flexDirection: 'row',

    alignItems: 'center',

    borderWidth: 1,

    borderColor: colors.surfaceVariant,

    borderRadius: radii.lg,

    backgroundColor: colors.surfaceContainerLow,

    minHeight: touchTargetMin,

    paddingHorizontal: spacing.md,

  },

  inputRowError: {

    borderColor: colors.error,

  },

  prefix: {

    fontSize: 16,

    fontWeight: '600',

    color: colors.onSurface,

    marginRight: spacing.sm,

  },

  input: {

    flex: 1,

    fontSize: 16,

    color: colors.onSurface,

    paddingVertical: spacing.sm,

  },

  errorText: {

    ...typography.caption,

    color: colors.error,

    marginTop: spacing.sm,

  },

  submit: {

    marginTop: spacing.lg,

  },

});


