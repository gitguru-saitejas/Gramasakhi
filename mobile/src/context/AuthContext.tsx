import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { isTokenResponse, registerCitizen as apiRegisterCitizen, sendOtp, validateSession, verifyOtp } from '../api/auth';
import type { TokenResponse } from '../api/types';
import {
  clearAuthSession,
  getAccessToken,
  getCitizenAccountId,
  getPhoneNumber,
  setAccessToken,
  setCitizenAccountId,
  setPhoneNumber,
  setDisplayName,
} from '../storage/authTokens';
import { ApiClientError, friendlyErrorMessage } from '../utils/errors';

export type AuthStatus = 'loading' | 'authenticated' | 'unauthenticated';

interface AuthContextValue {
  status: AuthStatus;
  citizenAccountId: string | null;
  phoneNumber: string | null;
  bootstrap: () => Promise<void>;
  requestOtp: (phone: string) => Promise<void>;
  verifyOtpCode: (phone: string, code: string) => Promise<{ needsRegistration: boolean }>;
  completeRegistration: (phone: string, displayName?: string) => Promise<void>;
  logout: () => Promise<void>;
  expireSession: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

async function persistSession(data: TokenResponse, phone: string): Promise<void> {
  const accountId = String(data.citizen_account_id || data.family_account_id || '');
  await setAccessToken(data.accessToken);
  if (accountId) await setCitizenAccountId(accountId);
  if (data.phone_number || phone) await setPhoneNumber(data.phone_number || phone);
  const name = (data.display_name || '').trim();
  if (name) await setDisplayName(name);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>('loading');
  const [citizenAccountId, setCitizenAccountIdState] = useState<string | null>(null);
  const [phoneNumber, setPhoneNumberState] = useState<string | null>(null);

  const bootstrap = useCallback(async () => {
    setStatus('loading');
    try {
      const token = await getAccessToken();
      if (!token) {
        setCitizenAccountIdState(null);
        setPhoneNumberState(null);
        setStatus('unauthenticated');
        return;
      }
      const valid = await validateSession(token);
      if (!valid) {
        await clearAuthSession();
        setCitizenAccountIdState(null);
        setPhoneNumberState(null);
        setStatus('unauthenticated');
        return;
      }
      const [accountId, phone] = await Promise.all([getCitizenAccountId(), getPhoneNumber()]);
      setCitizenAccountIdState(accountId);
      setPhoneNumberState(phone);
      setStatus('authenticated');
    } catch {
      const token = await getAccessToken();
      if (token) {
        const [accountId, phone] = await Promise.all([getCitizenAccountId(), getPhoneNumber()]);
        setCitizenAccountIdState(accountId);
        setPhoneNumberState(phone);
        setStatus('authenticated');
        return;
      }
      setStatus('unauthenticated');
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  const requestOtp = useCallback(async (phone: string) => {
    try {
      await sendOtp(phone);
    } catch (err) {
      if (err instanceof ApiClientError && err.status === 429) {
        throw new ApiClientError('Too many OTP requests. Please wait before trying again.', 429);
      }
      throw new ApiClientError(friendlyErrorMessage(err, 'Failed to send OTP. Please try again.'));
    }
  }, []);

  const completeRegistration = useCallback(async (phone: string, displayName?: string) => {
    try {
      const data = await apiRegisterCitizen({
        credentials: { phone_number: phone },
        display_name: displayName?.trim() || undefined,
      });
      await persistSession(data, phone);
      setCitizenAccountIdState(String(data.citizen_account_id || data.family_account_id || ''));
      setPhoneNumberState(data.phone_number || phone);
      setStatus('authenticated');
    } catch (err) {
      if (err instanceof ApiClientError) throw err;
      throw new ApiClientError(friendlyErrorMessage(err, 'Registration failed. Please try again.'));
    }
  }, []);

  const verifyOtpCode = useCallback(async (phone: string, code: string) => {
    try {
      const data = await verifyOtp(phone, code);
      if (isTokenResponse(data)) {
        await persistSession(data, phone);
        setCitizenAccountIdState(String(data.citizen_account_id || data.family_account_id || ''));
        setPhoneNumberState(data.phone_number || phone);
        setStatus('authenticated');
        return { needsRegistration: false };
      }
      return { needsRegistration: true };
    } catch (err) {
      if (err instanceof ApiClientError) throw err;
      throw new ApiClientError(friendlyErrorMessage(err, 'Invalid OTP code.'));
    }
  }, []);

  const logout = useCallback(async () => {
    await clearAuthSession();
    setCitizenAccountIdState(null);
    setPhoneNumberState(null);
    setStatus('unauthenticated');
  }, []);

  const expireSession = useCallback(async () => {
    await clearAuthSession();
    setCitizenAccountIdState(null);
    setPhoneNumberState(null);
    setStatus('unauthenticated');
  }, []);

  const getToken = useCallback(() => getAccessToken(), []);

  const value = useMemo(
    () => ({
      status,
      citizenAccountId,
      phoneNumber,
      bootstrap,
      requestOtp,
      verifyOtpCode,
      completeRegistration,
      logout,
      expireSession,
      getToken,
    }),
    [status, citizenAccountId, phoneNumber, bootstrap, requestOtp, verifyOtpCode, completeRegistration, logout, expireSession, getToken]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
