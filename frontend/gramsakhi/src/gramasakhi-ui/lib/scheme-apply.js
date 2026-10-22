import { safeHttpUrl } from '@/lib/utils';

/** Resolve Apply Online target from API scheme_apply + message meta (trusted URLs only). */
export function resolveSchemeApplyTarget({ scheme, meta, raw, sources = [] }) {
  const apply = raw?.scheme_apply || meta?.scheme_apply || scheme?.apply || null;
  let applicationUrl = safeHttpUrl(apply?.application_url);
  let informationUrl = safeHttpUrl(apply?.official_information_url);

  if (!applicationUrl && meta) {
    applicationUrl =
      safeHttpUrl(meta?.action_plan?.application_url) ||
      safeHttpUrl(meta?.scheme_guidance?.application_url);
  }
  if (!informationUrl && apply?.scheme_id) {
    informationUrl = safeHttpUrl(
      `https://www.myscheme.gov.in/schemes/${String(apply.scheme_id).trim()}`
    );
  }
  if (!applicationUrl && !informationUrl) {
    for (const s of sources || []) {
      const url = safeHttpUrl(s?.url);
      if (!url) continue;
      const low = url.toLowerCase();
      if (low.includes('myscheme.gov.in/schemes/')) {
        informationUrl = informationUrl || url;
      }
      if (/apply|registration|register|sevasindhu|portal/.test(low) && low.includes('gov')) {
        applicationUrl = url;
        break;
      }
    }
  }

  if (applicationUrl) {
    return { url: applicationUrl, kind: 'application' };
  }
  if (informationUrl) {
    return { url: informationUrl, kind: 'official_information' };
  }
  return null;
}

export function openExternalApplyUrl(url) {
  const safe = safeHttpUrl(url);
  if (!safe) return false;
  window.open(safe, '_blank', 'noopener,noreferrer');
  return true;
}
