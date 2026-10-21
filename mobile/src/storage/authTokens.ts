import { secureGet, secureRemove, secureSet } from './secureStorage';

const ACCESS_TOKEN_KEY = 'gramsakhi.accessToken';
const CITIZEN_ACCOUNT_ID_KEY = 'gramsakhi.citizenAccountId';
const PHONE_NUMBER_KEY = 'gramsakhi.phoneNumber';
const DISPLAY_NAME_KEY = 'gramsakhi.displayName';
const CONVERSATION_ID_KEY = 'gramsakhi.conversationId';

/** Read stored access token (never log the return value). */
export async function getAccessToken(): Promise<string | null> {
  return secureGet(ACCESS_TOKEN_KEY);
}

export async function setAccessToken(token: string): Promise<void> {
  await secureSet(ACCESS_TOKEN_KEY, token);
}

export async function clearAccessToken(): Promise<void> {
  await secureRemove(ACCESS_TOKEN_KEY);
}

export async function getCitizenAccountId(): Promise<string | null> {
  return secureGet(CITIZEN_ACCOUNT_ID_KEY);
}

export async function setCitizenAccountId(id: string): Promise<void> {
  await secureSet(CITIZEN_ACCOUNT_ID_KEY, id);
}

export async function clearCitizenAccountId(): Promise<void> {
  await secureRemove(CITIZEN_ACCOUNT_ID_KEY);
}

export async function getPhoneNumber(): Promise<string | null> {
  return secureGet(PHONE_NUMBER_KEY);
}

export async function setPhoneNumber(phone: string): Promise<void> {
  await secureSet(PHONE_NUMBER_KEY, phone);
}

export async function clearPhoneNumber(): Promise<void> {
  await secureRemove(PHONE_NUMBER_KEY);
}

export async function getDisplayName(): Promise<string | null> {
  return secureGet(DISPLAY_NAME_KEY);
}

export async function setDisplayName(name: string): Promise<void> {
  await secureSet(DISPLAY_NAME_KEY, name);
}

export async function clearDisplayName(): Promise<void> {
  await secureRemove(DISPLAY_NAME_KEY);
}

export async function clearConversationId(): Promise<void> {
  await secureRemove(CONVERSATION_ID_KEY);
}

export async function getConversationId(): Promise<string | null> {
  return secureGet(CONVERSATION_ID_KEY);
}

export async function setConversationId(id: string): Promise<void> {
  await secureSet(CONVERSATION_ID_KEY, id);
}

export async function clearAuthSession(): Promise<void> {
  await Promise.all([
    clearAccessToken(),
    clearCitizenAccountId(),
    clearPhoneNumber(),
    clearDisplayName(),
    clearConversationId(),
  ]);
}
