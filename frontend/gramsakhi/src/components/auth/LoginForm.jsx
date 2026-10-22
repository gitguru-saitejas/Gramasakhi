import React, { useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { MobileInput } from "./MobileInput";
import api from "../../services/api";
import { Loader2 } from "lucide-react";

const phoneSchema = z.object({
  phone_number: z.string().length(10, "Mobile number must be exactly 10 digits"),
});

export const LoginForm = () => {
  const [sendingOtp, setSendingOtp] = useState(false);
  const { showToast } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const returnTo = location.state?.from || "/chat";

  const {
    control,
    handleSubmit,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(phoneSchema),
    defaultValues: { phone_number: "" },
  });

  const onSendOtp = async ({ phone_number }) => {
    setSendingOtp(true);
    try {
      const res = await api.post("/auth/otp/send", { phone_number }, { skipErrorToast: true });
      localStorage.setItem("tempPhone", phone_number);
      showToast("success", res.data?.message || "OTP sent successfully!");
      const data = res.data || {};
      const otpSession =
        data.delivery_mode === "dev_popup" && data.dev_otp
          ? {
              deliveryMode: data.delivery_mode,
              devOtp: data.dev_otp,
              devNotice: data.dev_notice,
              otpVerificationId: data.otp_verification_id,
              expiresInSeconds: data.expires_in_seconds,
            }
          : {
              deliveryMode: data.delivery_mode || "sms",
              otpVerificationId: data.otp_verification_id,
              expiresInSeconds: data.expires_in_seconds,
            };
      // Phone travels via navigation state + tempPhone, never in the URL
      // (query strings end up in browser history and server access logs).
      navigate("/citizen/verify-otp", {
        state: { from: returnTo, phone: phone_number, otpSession },
      });
    } catch (err) {
      const msg = err.response?.data?.detail || "Failed to send OTP.";
      showToast("error", msg);
    } finally {
      setSendingOtp(false);
    }
  };

  return (
    <div className="w-full bg-surface-container-lowest border border-surface-variant shadow-ambient rounded-[32px] p-6 sm:p-8">
      <form onSubmit={handleSubmit(onSendOtp)} className="space-y-5">
        <Controller
          name="phone_number"
          control={control}
          render={({ field }) => (
            <MobileInput
              label="Mobile Number"
              error={errors.phone_number?.message}
              {...field}
            />
          )}
        />

        <button
          type="submit"
          disabled={sendingOtp}
          aria-busy={sendingOtp}
          className="w-full py-3 rounded-full bg-primary text-on-primary font-bold text-sm hover:bg-surface-tint disabled:opacity-60 transition-all active:scale-[0.98] focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          {sendingOtp ? <Loader2 className="h-4 w-4 animate-spin mx-auto" aria-hidden="true" /> : "Send OTP"}
        </button>
      </form>

      <p className="text-center text-sm text-on-surface-variant mt-4">
        New here?{" "}
        <Link
          to="/citizen/register"
          state={{ from: returnTo }}
          className="text-secondary font-bold hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 rounded"
        >
          Create citizen account
        </Link>
      </p>
    </div>
  );
};

export default LoginForm;
