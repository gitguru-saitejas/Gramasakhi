/**
 * Central API origin resolution for citizen + admin clients.
 * Secrets never belong here — only the public backend base URL.
 */

const LOCAL_DEFAULT = "http://127.0.0.1:8000";
/** Deployed FastAPI on Render (fallback when PROD build omits VITE_API_BASE_URL). */
const RENDER_DEFAULT = "https://gramasakhi.onrender.com";

export function resolveApiOrigin() {
  const raw =
    import.meta.env.VITE_API_BASE_URL ||
    import.meta.env.VITE_API_URL ||
    "";
  const trimmed = String(raw).trim().replace(/\/$/, "");
  if (trimmed) {
    return trimmed.replace(/\/api$/, "");
  }
  if (import.meta.env.PROD) {
    return RENDER_DEFAULT;
  }
  return LOCAL_DEFAULT;
}

/** Citizen API prefix: `{origin}/api` */
export function resolveCitizenApiBaseUrl(origin = resolveApiOrigin()) {
  const base = origin.replace(/\/$/, "");
  return base.endsWith("/api") ? base : `${base}/api`;
}

/** Super-admin API prefix: `{origin}/api/v1/super-admin` */
export function resolveAdminApiBaseUrl(origin = resolveApiOrigin()) {
  return `${resolveCitizenApiBaseUrl(origin)}/v1/super-admin`;
}

export function getConfiguredApiOrigin() {
  return resolveApiOrigin();
}
