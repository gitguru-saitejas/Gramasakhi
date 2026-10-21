import { apiRequest } from './client';
import { ApiClientError } from '../utils/errors';
import type { OtpSendResponse, OtpVerifyResponse, TokenResponse } from './types';

export async function sendOtp(phoneNumber: string): Promise<OtpSendResponse> {
  return apiRequest<OtpSendResponse>('/auth/otp/send', {
    method: 'POST',
    body: { phone_number: phoneNumber },
    skipAuth: true,
  });
}

export async function verifyOtp(phoneNumber: string, code: string): Promise<OtpVerifyResponse> {
  return apiRequest<OtpVerifyResponse>('/auth/otp/verify', {
    method: 'POST',
    body: { phone_number: phoneNumber, code },
    skipAuth: true,
  });
}

/** Lightweight session check using an existing authenticated endpoint. */
export async function validateSession(token: string): Promise<boolean> {
  try {
    await apiRequest<{ conversations: unknown[] }>('/chat/conversations?limit=1&offset=0', {
      token,
      timeoutMs: 12000,
    });
    return true;
  } catch (err) {
    if (err instanceof ApiClientError && (err.status === 401 || err.status === 403)) {
      return false;
    }
    throw err;
  }
}

export function isTokenResponse(data: OtpVerifyResponse): data is TokenResponse {
  return typeof data === 'object' && data !== null && 'accessToken' in data && Boolean(data.accessToken);
}

export interface RegisterRequest {
  credentials: { phone_number: string };
  display_name?: string;
}

export async function registerCitizen(payload: RegisterRequest): Promise<TokenResponse> {
  return apiRequest<TokenResponse>('/auth/register', {
    method: 'POST',
    body: payload,
    skipAuth: true,
  });
}
