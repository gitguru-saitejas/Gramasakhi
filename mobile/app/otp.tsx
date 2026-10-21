import { useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import { GramSakhiLogo } from '../src/components/GramSakhiLogo';
import { OtpInput } from '../src/components/OtpInput';
import { PrimaryButton } from '../src/components/PrimaryButton';
import { ScreenContainer } from '../src/components/ScreenContainer';
import { useAuth } from '../src/context/AuthContext';
import { useLanguage } from '../src/context/LanguageContext';
import { ApiClientError } from '../src/utils/errors';
import { friendlyErrorMessage } from '../src/utils/errors';
import { clearOtpFlowPhone, consumeOtpFlowPhone } from '../src/utils/otpFlowPhone';
import { colors, radii, spacing, touchTargetMin, typography } from '../src/theme';

const RESEND_SECONDS = 180;

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
}

export default function OtpScreen() {
  const router = useRouter();
  const [phoneNumber, setPhoneNumber] = useState('');
  const { verifyOtpCode, requestOtp, completeRegistration, status } = useAuth();
  const { t } = useLanguage();

  const [otp, setOtp] = useState('');
  const [timer, setTimer] = useState(RESEND_SECONDS);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [needsRegistration, setNeedsRegistration] = useState(false);
  const [displayName, setDisplayName] = useState('');
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    const phone = consumeOtpFlowPhone();
    if (!phone) {
      router.replace('/login');
      return;
    }
    setPhoneNumber(phone);
  }, [router]);

  useEffect(() => {
    if (!phoneNumber) return;
    if (status === 'authenticated' && !needsRegistration) {
      router.replace('/chat');
    }
  }, [status, router, needsRegistration]);

  useEffect(() => {
    if (timer <= 0 || success) return undefined;
    const interval = setInterval(() => setTimer((prev) => Math.max(0, prev - 1)), 1000);
    return () => clearInterval(interval);
  }, [timer, success]);

  const handleVerify = async () => {
    if (!otp || otp.length !== 6 || verifying) {
      if (otp.length !== 6) setOtpError(t('otp.invalidLength'));
      return;
    }
    setVerifying(true);
    setOtpError(null);
    try {
      const result = await verifyOtpCode(phoneNumber, otp);
      if (result.needsRegistration) {
        setNeedsRegistration(true);
        return;
      }
      setSuccess(true);
      setTimeout(() => router.replace('/chat'), 600);
    } catch (err) {
      setOtpError(
        err instanceof ApiClientError
          ? err.message
          : friendlyErrorMessage(err, t('otp.invalidCode'))
      );
    } finally {
      setVerifying(false);
    }
  };

  const handleCreateAccount = async () => {
    if (registering) return;
    setRegistering(true);
    setOtpError(null);
    try {
      await completeRegistration(phoneNumber, displayName);
      setSuccess(true);
      setNeedsRegistration(false);
      setTimeout(() => router.replace('/chat'), 600);
    } catch (err) {
      setOtpError(
        err instanceof ApiClientError
          ? err.message
          : friendlyErrorMessage(err, t('otp.registerFailed'))
      );
    } finally {
      setRegistering(false);
    }
  };

  const handleResend = async () => {
    if (timer > 0 || resending) return;
    setResending(true);
    setOtpError(null);
    try {
      await requestOtp(phoneNumber);
      setTimer(RESEND_SECONDS);
      setOtp('');
    } catch (err) {
      setOtpError(
        err instanceof ApiClientError
          ? err.message
          : friendlyErrorMessage(err, t('otp.resendFailed'))
      );
    } finally {
      setResending(false);
    }
  };

  if (!phoneNumber) return null;

  return (
    <ScreenContainer scroll={false}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t('otp.changeNumber')}
        onPress={() => {
          clearOtpFlowPhone();
          router.replace('/login');
        }}
        style={styles.changeNumber}
      >
        <Text style={styles.changeNumberText}>{t('otp.changeNumber')}</Text>
      </Pressable>

      <View style={styles.header}>
        <View style={styles.iconCircle}>
          {success ? (
            <MaterialCommunityIcons name="sprout" size={32} color={colors.primary} />
          ) : (
            <MaterialCommunityIcons name="cellphone" size={32} color={colors.primary} />
          )}
        </View>
        <Text style={styles.title} accessibilityRole="header">
          {success ? t('otp.signedIn') : t('otp.enterCode')}
        </Text>
        {!success ? (
          <Text style={styles.subtitle}>{t('otp.sentTo')} +91 {phoneNumber.slice(0, 2)}******{phoneNumber.slice(-2)}</Text>
        ) : null}
      </View>

      <View style={styles.card}>
        {needsRegistration ? (
          <View accessibilityRole="alert">
            <Text style={styles.registrationText}>{t('otp.notRegistered')}</Text>
            <Text style={styles.fieldLabel}>{t('otp.displayName')}</Text>
            <TextInput
              accessibilityLabel={t('otp.displayName')}
              placeholder={t('otp.displayNamePlaceholder')}
              value={displayName}
              onChangeText={setDisplayName}
              style={styles.nameInput}
              autoCapitalize="words"
            />
            {otpError ? <Text style={styles.inlineError}>{otpError}</Text> : null}
            <PrimaryButton
              label={t('otp.createAccount')}
              onPress={() => void handleCreateAccount()}
              loading={registering}
              buttonStyle={styles.verifyBtn}
            />
          </View>
        ) : success ? (
          <View style={styles.successBlock}>
            <MaterialCommunityIcons name="shield-check" size={40} color={colors.secondary} />
            <Text style={styles.successText}>{t('otp.opening')}</Text>
            <ActivityIndicator color={colors.secondary} />
          </View>
        ) : (
          <>
            <OtpInput
              value={otp}
              onChange={(val) => {
                setOtp(val);
                if (otpError) setOtpError(null);
              }}
              error={otpError}
              label={t('otp.enterOtp')}
            />

            <View style={styles.timerRow}>
              <View style={styles.timerLeft}>
                <MaterialCommunityIcons name="timer-outline" size={16} color={colors.onSurfaceVariant} />
                <Text style={styles.timerText}>{formatTime(timer)}</Text>
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t('otp.resend')}
                accessibilityState={{ disabled: timer > 0 || resending }}
                disabled={timer > 0 || resending}
                onPress={() => void handleResend()}
                style={styles.resendBtn}
              >
                {resending ? (
                  <ActivityIndicator size="small" color={colors.secondary} />
                ) : (
                  <MaterialCommunityIcons name="refresh" size={16} color={colors.secondary} />
                )}
                <Text style={[styles.resendText, (timer > 0 || resending) && styles.resendDisabled]}>
                  {t('otp.resend')}
                </Text>
              </Pressable>
            </View>

            <PrimaryButton
              label={t('otp.verifyContinue')}
              onPress={() => void handleVerify()}
              disabled={otp.length !== 6}
              loading={verifying}
              buttonStyle={styles.verifyBtn}
            />
          </>
        )}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  changeNumber: {
    minHeight: touchTargetMin,
    justifyContent: 'center',
    alignSelf: 'flex-end',
    paddingHorizontal: spacing.xs,
  },
  changeNumberText: {
    ...typography.caption,
    color: colors.secondary,
    fontWeight: '700',
  },
  header: {
    alignItems: 'center',
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  iconCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.surfaceContainerHigh,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: `${colors.surfaceVariant}99`,
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
    gap: spacing.md,
  },
  timerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.xs,
  },
  timerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  timerText: {
    ...typography.caption,
    color: colors.onSurfaceVariant,
    fontWeight: '600',
  },
  resendBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    minHeight: touchTargetMin,
    justifyContent: 'center',
  },
  resendText: {
    ...typography.caption,
    color: colors.secondary,
    fontWeight: '700',
  },
  resendDisabled: {
    opacity: 0.45,
  },
  verifyBtn: {
    marginTop: spacing.sm,
  },
  successBlock: {
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.md,
  },
  successText: {
    ...typography.body,
    textAlign: 'center',
  },
  registrationText: {
    ...typography.body,
    marginBottom: spacing.md,
    textAlign: 'center',
  },
  fieldLabel: {
    ...typography.caption,
    color: colors.onSurfaceVariant,
    fontWeight: '700',
    marginBottom: spacing.xs,
  },
  nameInput: {
    borderWidth: 1,
    borderColor: colors.surfaceVariant,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    ...typography.body,
    marginBottom: spacing.sm,
  },
  inlineError: {
    ...typography.caption,
    color: colors.error,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
});
