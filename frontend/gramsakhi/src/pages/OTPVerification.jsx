import React, { useState, useEffect } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { OTPInput } from "../components/auth/OTPInput";
import DevOtpSidePanel from "../components/auth/DevOtpSidePanel";
import { MarketingPage } from "../gramasakhi-ui/components/marketing/MarketingShell";
import api from "../services/api";
import {
  Smartphone,
  ShieldCheck,
  ArrowRight,
  Loader2,
  Timer,
  RotateCcw,
  CheckCircle2,
  Sprout,
} from "lucide-react";
import "../gramasakhi-ui/globals.css";

export default function OTPVerification() {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { loginWithOtp, showToast } = useAuth();

  const phoneFromQuery = searchParams.get("phone") || "";
  const phone = location.state?.phone || phoneFromQuery || localStorage.getItem("tempPhone") || "";
  const returnTo = location.state?.from || "/chat";

  const [otpSession, setOtpSession] = useState(() => location.state?.otpSession || null);
  const [otp, setOtp] = useState("");
  const [timer, setTimer] = useState(() => otpSession?.expiresInSeconds ?? 180);
  const [verifying, setVerifying] = useState(false);
  const [resending, setResending] = useState(false);
  const [otpError, setOtpError] = useState(null);
  const [success, setSuccess] = useState(false);
  const [copied, setCopied] = useState(false);

  const showDevPanel = Boolean(otpSession?.devOtp && otpSession?.deliveryMode === "dev_popup");

  useEffect(() => {
    if (!phone) {
      navigate("/citizen/login", { replace: true, state: { from: returnTo } });
    } else {
      localStorage.setItem("tempPhone", phone);
    }
  }, [phone, navigate, returnTo]);

  useEffect(() => {
    if (timer === 0 || success) return undefined;
    const interval = setInterval(() => setTimer((prev) => prev - 1), 1000);
    return () => clearInterval(interval);
  }, [timer, success]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  const applySendResponse = (data) => {
    if (!data) return;
    if (data.delivery_mode === "dev_popup" && data.dev_otp) {
      setOtpSession({
        deliveryMode: data.delivery_mode,
        devOtp: data.dev_otp,
        devNotice: data.dev_notice,
        otpVerificationId: data.otp_verification_id,
        expiresInSeconds: data.expires_in_seconds,
      });
    } else {
      setOtpSession({
        deliveryMode: data.delivery_mode || "sms",
        otpVerificationId: data.otp_verification_id,
        expiresInSeconds: data.expires_in_seconds,
        devOtp: null,
      });
    }
    if (typeof data.expires_in_seconds === "number") {
      setTimer(data.expires_in_seconds);
    }
  };

  const handleCopyDevOtp = async () => {
    if (!otpSession?.devOtp) return;
    try {
      await navigator.clipboard.writeText(otpSession.devOtp);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      showToast("error", "Could not copy to clipboard.");
    }
  };

  const handleVerify = async (e) => {
    e.preventDefault();
    if (!otp || otp.length !== 6) {
      setOtpError("OTP must be exactly 6 digits");
      return;
    }
    if (verifying) return;

    setVerifying(true);
    setOtpError(null);
    try {
      const result = await loginWithOtp(phone, otp, otpSession?.otpVerificationId || null);
      if (result?.needs_registration) {
        localStorage.setItem("tempPhone", phone);
        sessionStorage.setItem("citizenOtpVerifiedPhone", phone);
        navigate("/citizen/register", {
          state: { from: returnTo, phone },
        });
        return;
      }
      localStorage.removeItem("tempPhone");
      setSuccess(true);
      setTimeout(() => navigate(returnTo, { replace: true }), 600);
    } catch (err) {
      setOtpError(
        err.response?.data?.detail || err.response?.data?.message || "Invalid OTP code."
      );
    } finally {
      setVerifying(false);
    }
  };

  const handleResend = async () => {
    if (timer > 0 || resending) return;
    setResending(true);
    setOtpError(null);
    try {
      const res = await api.post("/auth/otp/send", { phone_number: phone }, { skipErrorToast: true });
      applySendResponse(res.data);
      setOtp("");
      showToast("success", "A new OTP code has been sent!");
    } catch (err) {
      showToast("error", err.response?.data?.detail || "Failed to resend OTP.");
    } finally {
      setResending(false);
    }
  };

  if (!phone) return null;

  return (
    <MarketingPage
      navRight={
        <Link
          to="/citizen/login"
          state={{ from: returnTo }}
          className="text-xs font-semibold text-secondary hover:text-primary transition-colors"
        >
          Change number
        </Link>
      }
    >
      <main className="pt-24 pb-12 min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 relative">
        <div className="absolute inset-0 bg-gradient-to-br from-surface-container-low via-background to-secondary-container/25 pointer-events-none" />

        <div className="relative w-full max-w-4xl flex flex-col lg:flex-row gap-6 lg:gap-8 items-stretch justify-center">
          <div className="w-full max-w-md mx-auto lg:mx-0 flex-shrink-0">
            <div className="text-center mb-6 space-y-3">
              <div className="w-16 h-16 bg-surface-container-high rounded-full mx-auto flex items-center justify-center shadow-ambient border border-surface-variant/50 relative">
                {!success ? (
                  <Smartphone className="w-8 h-8 text-primary" />
                ) : (
                  <Sprout className="w-8 h-8 text-primary" />
                )}
                <div className="absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full bg-secondary-container flex items-center justify-center">
                  <CheckCircle2 className="w-3 h-3 text-secondary" />
                </div>
              </div>
              <h1 className="text-2xl font-bold text-primary tracking-tight">
                {success ? "You're signed in" : "Enter verification code"}
              </h1>
              {!success && (
                <p className="text-sm text-on-surface-variant">OTP sent to +91 {phone}</p>
              )}
            </div>

            <div className="bg-surface-container-lowest border border-surface-variant shadow-ambient rounded-[32px] p-6 sm:p-8">
              {!success ? (
                <form onSubmit={handleVerify} className="space-y-6">
                  <OTPInput
                    value={otp}
                    onChange={(val) => {
                      setOtp(val);
                      if (otpError) setOtpError(null);
                    }}
                    error={otpError}
                    label="Enter OTP"
                  />

                  <div className="flex items-center justify-between text-sm px-1">
                    <div className="flex items-center gap-1.5 text-on-surface-variant font-medium">
                      <Timer className="h-4 w-4" />
                      <span>{formatTime(timer)}</span>
                    </div>
                    <button
                      type="button"
                      disabled={timer > 0 || resending}
                      onClick={handleResend}
                      className="flex items-center gap-1.5 font-bold text-secondary disabled:opacity-40 hover:underline focus:outline-none"
                    >
                      {resending ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="h-3.5 w-3.5" />
                      )}
                      Resend OTP
                    </button>
                  </div>

                  <button
                    type="submit"
                    disabled={verifying || otp.length !== 6}
                    aria-busy={verifying}
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-full bg-primary text-on-primary font-bold text-sm hover:bg-surface-tint disabled:opacity-50 transition-all active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                  >
                    {verifying ? (
                      <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
                    ) : (
                      <>
                        Verify & Sign In
                        <ArrowRight className="h-4 w-4" />
                      </>
                    )}
                  </button>
                </form>
              ) : (
                <div className="py-4 text-center space-y-3">
                  <ShieldCheck className="w-10 h-10 text-secondary mx-auto" />
                  <p className="text-sm text-on-surface-variant">Opening GramSakhi…</p>
                </div>
              )}
            </div>
          </div>

          {showDevPanel && !success && (
            <div className="w-full max-w-sm mx-auto lg:mx-0 lg:sticky lg:top-28 self-start">
              <DevOtpSidePanel
                devOtp={otpSession.devOtp}
                devNotice={otpSession.devNotice}
                expiresInSeconds={timer}
                onCopy={handleCopyDevOtp}
                copied={copied}
              />
            </div>
          )}
        </div>
      </main>
    </MarketingPage>
  );
}
