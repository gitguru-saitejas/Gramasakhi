/** Client-side citizen JWT session helpers (routing only; server still validates). */

export function decodeJwtPayload(token) {
  if (!token || typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length < 2) return null;
  try {
    const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function isCitizenAccessTokenValid(token) {
  const payload = decodeJwtPayload(token);
  if (!payload?.sub) return false;
  if (payload.token_use && payload.token_use !== "citizen") return false;
  if (payload.exp && Date.now() >= payload.exp * 1000) return false;
  return true;
}

export function clearCitizenSessionStorage() {
  localStorage.removeItem("accessToken");
  localStorage.removeItem("citizenAccountId");
  localStorage.removeItem("familyAccountId");
  localStorage.removeItem("citizenPhone");
  localStorage.removeItem("gramsakhiConversationId");
  sessionStorage.removeItem("gramsakhiForceNewChat");
  sessionStorage.removeItem("citizenOtpVerifiedPhone");
}
