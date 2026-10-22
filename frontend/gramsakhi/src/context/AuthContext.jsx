import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import api, { apiEvents } from "../services/api";
import { useChatStore } from "../gramasakhi-ui/stores/chat-store";
import { clearCitizenSessionStorage } from "../utils/citizenSession";
import {
  clearCitizenAuthMemory,
  getCitizenAccountId,
  getCitizenPhone,
  isCitizenSessionActive,
  setCitizenAuth,
} from "../services/auth-token";
import { syncCitizenProfileFromAuth } from "../utils/citizenProfile";

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
};

export const AuthProvider = ({ children }) => {
  const [citizenAccountId, setCitizenAccountId] = useState(null);
  const [phoneNumber, setPhoneNumber] = useState(null);
  const [authReady, setAuthReady] = useState(false);
  const [globalLoading, setGlobalLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");

  const invalidateCitizenSession = useCallback(() => {
    clearCitizenSessionStorage();
    clearCitizenAuthMemory();
    useChatStore.getState().resetSession();
    setCitizenAccountId(null);
    setPhoneNumber(null);
  }, []);

  useEffect(() => {
    clearCitizenSessionStorage();
    clearCitizenAuthMemory();
    setAuthReady(true);
  }, []);

  useEffect(() => {
    const unsubLoading = apiEvents.subscribe("loading", (isLoading) => setGlobalLoading(isLoading));
    const unsubToast = apiEvents.subscribe("toast", (msg) => {
      setToastMessage(msg);
      setTimeout(() => setToastMessage(null), 4000);
    });
    const unsubAuth = apiEvents.subscribe("auth-expired", () => {
      invalidateCitizenSession();
    });
    return () => {
      unsubLoading();
      unsubToast();
      unsubAuth();
    };
  }, [invalidateCitizenSession]);

  useEffect(() => {
    if (theme === "dark") document.documentElement.classList.add("dark");
    else document.documentElement.classList.remove("dark");
    localStorage.setItem("theme", theme);
  }, [theme]);

  const toggleTheme = () => setTheme((prev) => (prev === "light" ? "dark" : "light"));

  const showToast = (type, message) => {
    setToastMessage({ type, message });
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleLoginResponse = (data) => {
    sessionStorage.removeItem("citizenOtpVerifiedPhone");
    const accountId = data.citizen_account_id || data.family_account_id;
    setCitizenAuth({
      token: data.accessToken,
      accountId,
      phone: data.phone_number,
    });
    setCitizenAccountId(accountId);
    if (data.phone_number) {
      setPhoneNumber(data.phone_number);
    }
    syncCitizenProfileFromAuth(data);
    showToast("success", "Login successful!");
    return data;
  };

  const loginWithOtp = async (phone, code, otpVerificationId = null) => {
    const payload = { phone_number: phone, code };
    if (otpVerificationId) {
      payload.otp_verification_id = otpVerificationId;
    }
    const res = await api.post("/auth/otp/verify", payload);
    if (res.data?.accessToken) {
      return handleLoginResponse(res.data);
    }
    sessionStorage.setItem("citizenOtpVerifiedPhone", phone);
    showToast("success", res.data?.message || "OTP verified. Please create your account.");
    return { ...res.data, needs_registration: true, phone_number: phone };
  };

  const registerCitizen = async (registrationData) => {
    const phone = registrationData?.credentials?.phone_number;
    const verifiedPhone = sessionStorage.getItem("citizenOtpVerifiedPhone");
    if (!verifiedPhone || !phone || verifiedPhone !== phone) {
      throw Object.assign(new Error("OTP verification required"), {
        response: { data: { detail: "OTP verification is required before registration." } },
      });
    }
    const res = await api.post("/auth/register", registrationData);
    sessionStorage.removeItem("citizenOtpVerifiedPhone");
    if (res.data?.accessToken) {
      showToast("success", "Account created. Welcome to GramSakhi!");
      return handleLoginResponse(res.data);
    }
    showToast("success", "Account created. Please sign in with OTP.");
    return res.data;
  };

  const logout = () => {
    invalidateCitizenSession();
    showToast("success", "Logged out successfully.");
  };

  const clearToast = () => setToastMessage(null);

  const isAuthenticated = isCitizenSessionActive();

  return (
    <AuthContext.Provider
      value={{
        citizenAccountId: citizenAccountId || getCitizenAccountId(),
        phoneNumber: phoneNumber || getCitizenPhone(),
        authReady,
        isAuthenticated,
        globalLoading,
        toastMessage,
        theme,
        toggleTheme,
        showToast,
        clearToast,
        loginWithOtp,
        registerCitizen,
        logout,
        invalidateCitizenSession,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
