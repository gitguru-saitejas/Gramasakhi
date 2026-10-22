/**
 * In-memory citizen auth (web). Survives in-tab navigation only — not reload or new tab.
 */
import { isCitizenAccessTokenValid } from "../utils/citizenSession";

let accessToken = null;
let citizenAccountId = null;
let phoneNumber = null;

export function setCitizenAuth({ token, accountId, phone }) {
  accessToken = token || null;
  citizenAccountId = accountId || null;
  if (phone !== undefined) {
    phoneNumber = phone || null;
  }
}

export function getAccessToken() {
  return accessToken;
}

export function getCitizenAccountId() {
  return citizenAccountId;
}

export function getCitizenPhone() {
  return phoneNumber;
}

export function clearCitizenAuthMemory() {
  accessToken = null;
  citizenAccountId = null;
  phoneNumber = null;
}

export function isCitizenSessionActive() {
  return Boolean(
    citizenAccountId && accessToken && isCitizenAccessTokenValid(accessToken)
  );
}
