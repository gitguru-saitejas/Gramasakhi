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

const completeSchema = z.object({
  display_name: z.string().optional(),
  phone_number: z.string().length(10, "Mobile number must be exactly 10 digits"),
});

export const RegisterForm = () => {
  const { registerCitizen, showToast } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [sendingOtp, setSendingOtp] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const verifiedPhone = sessionStorage.getItem("citizenOtpVerifiedPhone") || "";
  const returnTo = location.state?.from || "/chat";
  const prefillPhone = location.state?.phone || verifiedPhone || "";

  const phoneForm = useForm({
    resolver: zodResolver(phoneSchema),
    defaultValues: { phone_number: prefillPhone },
  });

  const completeForm = useForm({
    resolver: zodResolver(completeSchema),
    defaultValues: { display_name: "", phone_number: verifiedPhone || prefillPhone },
  });

  const onSendOtp = async ({ phone_number }) => {
    setSendingOtp(true);
    try {
      const res = await api.post("/auth/otp/send", { phone_number }, { skipErrorToast: true });
      localStorage.setItem("tempPhone", phone_number);
      showToast("success", res.data?.message || "OTP sent successfully!");
      navigate("/citizen/verify-otp", {
        state: { from: returnTo, phone: phone_number, intent: "register" },
      });
    } catch (err) {
      showToast("error", err.response?.data?.detail || "Failed to send OTP.");
    } finally {
      setSendingOtp(false);
    }
  };

  const onCompleteRegistration = async (data) => {
    setSubmitting(true);
    try {
      await registerCitizen({
        credentials: { phone_number: data.phone_number },
        display_name: data.display_name?.trim() || undefined,
      });
      navigate(returnTo, { replace: true });
    } catch (err) {
      showToast("error", err.response?.data?.detail || "Registration failed.");
    } finally {
      setSubmitting(false);
    }
  };

  if (!verifiedPhone) {
    return (
      <div className="w-full max-w-md bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 shadow-xl rounded-3xl p-6 sm:p-8">
        <div className="text-center mb-6">
          <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Create GramSakhi account</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5">
            Enter your mobile number. We will send a one-time code to verify it.
          </p>
        </div>

        <form onSubmit={phoneForm.handleSubmit(onSendOtp)} className="space-y-4">
          <Controller
            name="phone_number"
            control={phoneForm.control}
            render={({ field }) => (
              <MobileInput
                label="Mobile Number"
                error={phoneForm.formState.errors.phone_number?.message}
                {...field}
              />
            )}
          />

          <button
            type="submit"
            disabled={sendingOtp}
            aria-busy={sendingOtp}
            className="w-full py-3 rounded-xl bg-emerald-700 text-white font-semibold text-sm hover:bg-emerald-800 disabled:opacity-60"
          >
            {sendingOtp ? <Loader2 className="h-4 w-4 animate-spin mx-auto" aria-hidden="true" /> : "Send OTP"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-500 mt-6">
          Already have an account?{" "}
          <Link to="/citizen/login" className="text-emerald-700 font-semibold hover:underline">
            Sign in with OTP
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="w-full max-w-md bg-white dark:bg-slate-900 border border-slate-100 dark:border-slate-800 shadow-xl rounded-3xl p-6 sm:p-8">
      <div className="text-center mb-6">
        <h2 className="text-2xl font-bold text-slate-800 dark:text-slate-100">Finish your account</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1.5">Your mobile number is verified.</p>
      </div>

      <form onSubmit={completeForm.handleSubmit(onCompleteRegistration)} className="space-y-4">
        <Controller
          name="phone_number"
          control={completeForm.control}
          render={({ field }) => (
            <MobileInput label="Mobile Number" error={completeForm.formState.errors.phone_number?.message} {...field} readOnly />
          )}
        />

        <div>
          <label htmlFor="register-display-name" className="text-xs font-bold text-slate-500 uppercase">
            Full name (optional)
          </label>
          <input
            id="register-display-name"
            {...completeForm.register("display_name")}
            autoComplete="name"
            className="mt-1 w-full px-3 py-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-transparent text-sm"
          />
        </div>

        <button
          type="submit"
          disabled={submitting}
          aria-busy={submitting}
          className="w-full py-3 rounded-xl bg-emerald-700 text-white font-semibold text-sm hover:bg-emerald-800 disabled:opacity-60"
        >
          {submitting ? <Loader2 className="h-4 w-4 animate-spin mx-auto" aria-hidden="true" /> : "Create account"}
        </button>
      </form>
    </div>
  );
};

export default RegisterForm;
