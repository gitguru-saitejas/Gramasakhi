/** Shared API response shapes matching the existing GramSakhi backend. */

export interface HealthResponse {
  status: string;
  service: string;
}

export interface TokenResponse {
  accessToken: string;
  citizen_account_id: string;
  family_account_id?: string; // compatibility alias of citizen_account_id
  phone_number?: string;
  display_name?: string | null;
}

export interface OtpSendRequest {
  phone_number: string;
}

export interface OtpSendResponse {
  message: string;
}

export interface OtpVerifyRequest {
  phone_number: string;
  code: string;
}

export type OtpVerifyResponse = TokenResponse | { message: string };

export interface ConversationListResponse {
  conversations: unknown[];
  total: number;
}

export interface LoginRequest {
  phone_number: string;
  password?: string;
  login_type: 'password' | 'otp';
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface ApiRequestOptions {
  method?: HttpMethod;
  body?: unknown;
  token?: string | null;
  timeoutMs?: number;
  skipAuth?: boolean;
}
