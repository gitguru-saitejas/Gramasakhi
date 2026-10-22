# Development OTP popup (FYP / local demo)

GramSakhi can show the generated OTP in the **verify-otp side panel** instead of relying on SMS or reading terminal logs.

## Enable (development only)

In `backend/.env`:

```env
APP_ENV=development
OTP_DELIVERY_MODE=dev_popup
OTP_DEV_POPUP_ENABLED=true
```

Restart the backend after changing these values.

## SMS mode (default / production)

```env
APP_ENV=production
OTP_DELIVERY_MODE=sms
OTP_DEV_POPUP_ENABLED=false
```

The API **never** includes `dev_otp` in SMS or production mode. OTPs are dispatched via `otp_sms` (provider hook; configure Exotel/etc. when ready).

## Flow

1. Citizen enters mobile on `/citizen/login` and clicks **Send OTP**.
2. Backend creates the usual `otp_verifications` row (expiry, attempt limits, rate limits unchanged).
3. In `dev_popup` mode, `POST /api/auth/otp/send` returns `dev_otp`, `otp_verification_id`, and `expires_in_seconds`.
4. The verify page shows the side panel with the demo notice.
5. User enters the code; frontend calls `POST /api/auth/otp/verify` (optionally with `otp_verification_id`).
6. JWT / registration flow is unchanged.

## Security

- Production startup **fails** if `OTP_DELIVERY_MODE=dev_popup` or `OTP_DEV_POPUP_ENABLED=true`.
- The frontend never reads `.dev_otp_last.txt`.
- Do not put OTPs in URLs or client storage (navigation state is in-memory for the session only).
- Popup mode **does not prove phone ownership** — use only for demos.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| No side panel | Check `OTP_DELIVERY_MODE=dev_popup`, restart backend, hard-refresh browser |
| OTP expired | Resend OTP (3-minute expiry) |
| Too many requests | Wait for rate-limit window |
| Backend won't start | Production + dev_popup — switch to `sms` |

See also: [OTP_DEV_RETRIEVAL.md](./OTP_DEV_RETRIEVAL.md) (legacy dev HTTP lookup).
