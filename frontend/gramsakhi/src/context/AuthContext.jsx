import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import api, { apiEvents } from "../services/api";
import { useChatStore } from "../gramasakhi-ui/stores/chat-store";
import { clearCitizenSessionStorage, isCitizenAccessTokenValid } from "../utils/citizenSession";
import { syncCitizenProfileFromAuth } from "../utils/citizenProfile";

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
};

export const AuthProvider = ({ children }) => {
  const [citizenAccountId, setCitizenAccountId] = useState(
    () => localStorage.getItem("citizenAccountId") || localStorage.getItem("familyAccountId") || null
  );
  const [phoneNumber, setPhoneNumber] = useState(() => localStorage.getItem("citizenPhone") || null);
  const [globalLoading, setGlobalLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");

  const invalidateCitizenSession = useCallback(() => {
    clearCitizenSessionStorage();
    useChatStore.getState().resetSession();
    setCitizenAccountId(null);
    setPhoneNumber(null);
  }, []);

  useEffect(() => {
    const token = localStorage.getItem("accessToken");
    const accountId =
      localStorage.getItem("citizenAccountId") || localStorage.getItem("familyAccountId");
    if (accountId && token && !isCitizenAccessTokenValid(token)) {
      invalidateCitizenSession();
    }
  }, [invalidateCitizenSession]);

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
    localStorage.setItem("accessToken", data.accessToken);
    localStorage.setItem("citizenAccountId", accountId);
    if (data.family_account_id || accountId) {
      localStorage.setItem("familyAccountId", accountId);
    }
    if (data.phone_number) {
      localStorage.setItem("citizenPhone", data.phone_number);
      setPhoneNumber(data.phone_number);
    }
    setCitizenAccountId(accountId);
    syncCitizenProfileFromAuth(data);
    showToast("success", "Login successful!");
    return data;
  };

  const loginWithOtp = async (phone, code) => {
    const res = await api.post("/auth/otp/verify", {
      phone_number: phone,
      code,
    });
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

  return (
    <AuthContext.Provider
      value={{
        citizenAccountId,
        phoneNumber,
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
