import { StyleSheet, Text, View } from 'react-native';
import { MaterialCommunityIcons } from '@expo/vector-icons';
import type { AssistanceMeta } from '../../types/chat';
import { useLanguage } from '../../context/LanguageContext';
import { colors, radii, spacing, typography } from '../../theme';

interface AssistanceMetaPanelProps {
  meta?: AssistanceMeta | null;
}

function statusColor(status?: string | null): { bg: string; text: string } {
  const raw = (status || '').trim();
  const s = raw.toLowerCase().replace(/-/g, '_');
  const upper = raw.toUpperCase();
  if (s === 'eligible' || upper === 'ELIGIBLE') {
    return { bg: colors.secondaryContainer, text: colors.onSecondaryContainer };
  }
  if (s === 'ineligible' || s === 'not_eligible' || upper === 'NOT_ELIGIBLE') {
    return { bg: colors.errorContainer, text: colors.onErrorContainer };
  }
  if (s === 'uncertain' || s === 'cannot_determine' || upper === 'CANNOT_DETERMINE') {
    return { bg: colors.surfaceContainerHigh, text: colors.onSurfaceVariant };
  }
  return { bg: colors.surfaceContainerHigh, text: colors.onSurfaceVariant };
}

export function AssistanceMetaPanel({ meta }: AssistanceMetaPanelProps) {
  const { t } = useLanguage();

  if (!meta) return null;

  const plan = meta.action_plan as Record<string, unknown> | null | undefined;
  const guidance = meta.scheme_guidance as Record<string, unknown> | null | undefined;
  const stepsRaw = guidance?.application_steps || plan?.steps;
  const steps = Array.isArray(stepsRaw)
    ? stepsRaw
        .slice(0, 5)
        .map((s) => (typeof s === 'string' ? s : String((s as { text?: string })?.text || '')))
        .filter(Boolean)
    : [];
  const nextStep = typeof plan?.next_step === 'string' ? plan.next_step : null;
  const statusStyle = statusColor(meta.eligibility_status);

  const hasContent =
    meta.detected_scheme ||
    meta.eligibility_status ||
    meta.eligibility_question ||
    (meta.missing_information && meta.missing_information.length > 0) ||
    steps.length > 0 ||
    nextStep;

  if (!hasContent) return null;

  return (
    <View style={styles.wrap} accessibilityLabel="Assistance details">
      {meta.detected_scheme ? (
        <View style={styles.row}>
          <MaterialCommunityIcons name="bank" size={14} color={colors.secondary} />
          <Text style={styles.scheme}>{meta.detected_scheme}</Text>
        </View>
      ) : null}

      {meta.eligibility_status ? (
        <View style={[styles.badge, { backgroundColor: statusStyle.bg }]}>
          <Text style={[styles.badgeText, { color: statusStyle.text }]}>
            {meta.eligibility_status.replace(/_/g, ' ')}
          </Text>
        </View>
      ) : null}

      {meta.eligibility_session_active && meta.eligibility_question ? (
        <Text style={styles.hint}>{t('meta.next')} {meta.eligibility_question.replace(/_/g, ' ')}</Text>
      ) : null}

      {meta.missing_information && meta.missing_information.length > 0 ? (
        <Text style={styles.hint}>{t('meta.stillNeeded')} {meta.missing_information.join(', ')}</Text>
      ) : null}

      {(nextStep || steps.length > 0) && (
        <View style={styles.planBox}>
          <Text style={styles.planTitle}>{t('meta.nextSteps')}</Text>
          {nextStep ? <Text style={styles.planItem}>{nextStep}</Text> : null}
          {steps.map((step, idx) => (
            <Text key={`step-${idx}`} style={styles.planItem}>
              {idx + 1}. {step}
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginTop: spacing.md,
    paddingTop: spacing.md,
    borderTopWidth: 1,
    borderTopColor: `${colors.surfaceVariant}99`,
    gap: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  scheme: {
    ...typography.caption,
    fontWeight: '700',
    color: colors.primary,
  },
  badge: {
    alignSelf: 'flex-start',
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'capitalize',
  },
  hint: {
    ...typography.caption,
    color: colors.onSurfaceVariant,
  },
  planBox: {
    backgroundColor: colors.surfaceContainerLow,
    borderRadius: radii.lg,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: `${colors.secondary}44`,
    gap: 4,
  },
  planTitle: {
    ...typography.caption,
    fontWeight: '700',
    color: colors.secondary,
    textTransform: 'uppercase',
  },
  planItem: {
    ...typography.caption,
    color: colors.onSurface,
  },
});
