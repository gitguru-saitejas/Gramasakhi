import React from "react";
import { AlertTriangle, Copy, Check } from "lucide-react";

/**
 * Development-only OTP display (data from POST /auth/otp/send when delivery_mode=dev_popup).
 * Never reads local files or client-side secrets.
 */
export function DevOtpSidePanel({
  devOtp,
  devNotice,
  expiresInSeconds,
  onCopy,
  copied,
  className = "",
}) {
  if (!devOtp) return null;

  const mins = Math.max(0, Math.floor((expiresInSeconds || 0) / 60));
  const secs = Math.max(0, (expiresInSeconds || 0) % 60);

  return (
    <aside
      className={`dev-otp-panel border border-amber-500/40 bg-amber-50 dark:bg-amber-950/30 rounded-2xl p-4 shadow-ambient ${className}`}
      aria-label="Development OTP helper"
      role="complementary"
    >
      <div className="flex gap-2 items-start mb-3">
        <AlertTriangle className="h-5 w-5 text-amber-600 shrink-0 mt-0.5" aria-hidden="true" />
        <p className="text-xs font-medium text-amber-900 dark:text-amber-100 leading-snug">
          {devNotice ||
            "Development demo — simulated phone verification. This does not verify ownership of your phone number."}
        </p>
      </div>
      <p className="text-[11px] uppercase tracking-wide text-amber-800/80 dark:text-amber-200/80 mb-1">
        Demo OTP
      </p>
      <div className="flex items-center justify-between gap-3">
        <span
          className="font-mono text-2xl font-bold tracking-[0.35em] text-primary tabular-nums"
          data-testid="dev-otp-code"
        >
          {devOtp}
        </span>
        <button
          type="button"
          onClick={onCopy}
          className="shrink-0 inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-bold bg-surface-container-high border border-surface-variant hover:bg-surface-container focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      {expiresInSeconds != null && (
        <p className="text-xs text-on-surface-variant mt-3">
          Expires in ~{mins}:{secs < 10 ? `0${secs}` : secs}
        </p>
      )}
    </aside>
  );
}

export default DevOtpSidePanel;
