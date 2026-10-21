import React from "react";

import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";

import { AuthProvider, useAuth } from "./context/AuthContext";

import Landing from "./landing/Landing";

import Login from "./pages/Login";

import Register from "./pages/Register";

import OTPVerification from "./pages/OTPVerification";

import GramSakhiChat from "./pages/GramSakhiChat";

import AdminShell from "./admin/AdminShell";

import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";

import {

  clearCitizenSessionStorage,

  isCitizenAccessTokenValid,

} from "./utils/citizenSession";

import "./admin/App.css";



const CitizenProtected = ({ children }) => {

  const { citizenAccountId, invalidateCitizenSession } = useAuth();

  const location = useLocation();

  const token = localStorage.getItem("accessToken");

  const sessionValid =

    Boolean(citizenAccountId && token) && isCitizenAccessTokenValid(token);



  if (!sessionValid) {

    if (token || citizenAccountId) {

      invalidateCitizenSession();

    } else {

      clearCitizenSessionStorage();

    }

    return (

      <Navigate

        to="/citizen/login"

        replace

        state={{ from: location.pathname + location.search }}

      />

    );

  }

  return children;

};



/** Auth pages always render; a stored JWT must not auto-redirect away from login/register. */

const CitizenAuthPage = ({ children }) => children;



const LandingRoute = () => {

  const { citizenAccountId } = useAuth();

  const token = localStorage.getItem("accessToken");

  if (citizenAccountId && token && isCitizenAccessTokenValid(token)) {

    return <Navigate to="/chat" replace />;

  }

  return <Landing />;

};



const GlobalToast = () => {

  const { toastMessage, clearToast } = useAuth();

  if (!toastMessage) return null;



  const getIcon = () => {

    switch (toastMessage.type) {

      case "success":

        return <CheckCircle2 className="h-5 w-5 shrink-0" />;

      case "error":

        return <AlertCircle className="h-5 w-5 shrink-0" />;

      default:

        return <Info className="h-5 w-5 shrink-0" />;

    }

  };



  return (

    <div

      role="status"

      aria-live="polite"

      className="fixed top-5 right-5 z-[60] max-w-sm w-full p-4 border rounded-2xl flex items-start gap-3 shadow-lg animate-in slide-in-from-top-5 duration-300 backdrop-blur-md opacity-98 select-none border-transparent text-white bg-slate-900/90"

    >

      <div className="text-blue-400">{getIcon()}</div>

      <div className="flex-1 text-xs font-semibold leading-relaxed pr-2">{toastMessage.message}</div>

      <button

        type="button"

        onClick={clearToast}

        aria-label="Dismiss notification"

        className="text-slate-400 hover:text-white transition focus:outline-none focus-visible:ring-2 focus-visible:ring-white/40 rounded"

      >

        <X className="h-4 w-4" />

      </button>

    </div>

  );

};



export default function App() {

  return (

    <AuthProvider>

      <BrowserRouter>

        <Routes>

          <Route path="/" element={<LandingRoute />} />



          <Route

            path="/citizen/login"

            element={

              <CitizenAuthPage>

                <Login />

              </CitizenAuthPage>

            }

          />

          <Route

            path="/citizen/register"

            element={

              <CitizenAuthPage>

                <Register />

              </CitizenAuthPage>

            }

          />

          <Route

            path="/citizen/verify-otp"

            element={

              <CitizenAuthPage>

                <OTPVerification />

              </CitizenAuthPage>

            }

          />



          <Route path="/login" element={<Navigate to="/citizen/login" replace />} />

          <Route path="/register" element={<Navigate to="/citizen/register" replace />} />

          <Route path="/forgot-password" element={<Navigate to="/citizen/login" replace />} />

          <Route path="/citizen/forgot-password" element={<Navigate to="/citizen/login" replace />} />

          <Route path="/verify-otp" element={<Navigate to="/citizen/verify-otp" replace />} />



          <Route

            path="/chat"

            element={

              <CitizenProtected>

                <GramSakhiChat />

              </CitizenProtected>

            }

          />

          <Route

            path="/chat/:conversationId"

            element={

              <CitizenProtected>

                <GramSakhiChat />

              </CitizenProtected>

            }

          />



          <Route path="/admin/*" element={<AdminShell />} />



          <Route path="*" element={<Navigate to="/" replace />} />

        </Routes>

        <GlobalToast />

      </BrowserRouter>

    </AuthProvider>

  );

}


