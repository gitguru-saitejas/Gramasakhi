import React from "react";
import { Link } from "react-router-dom";
import { LoginForm } from "../components/auth/LoginForm";
import { MarketingPage } from "../gramasakhi-ui/components/marketing/MarketingShell";
import { CheckCircle2, Sprout } from "lucide-react";
import "../gramasakhi-ui/globals.css";

export default function Login() {
  return (
    <MarketingPage
      navRight={
        <Link
          to="/"
          className="text-xs font-semibold text-secondary hover:text-primary transition-colors focus:outline-none focus-visible:underline"
        >
          Back to home
        </Link>
      }
    >
      <main className="pt-24 pb-12 min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 relative">
        <div className="absolute inset-0 bg-gradient-to-br from-surface-container-low via-background to-secondary-container/25 pointer-events-none" />
        <div className="absolute -left-20 bottom-10 w-64 h-64 rounded-full bg-primary/5 blur-3xl pointer-events-none" />

        <div className="relative w-full max-w-md space-y-6">
          <div className="text-center space-y-3">
            <div className="w-16 h-16 bg-surface-container-high rounded-full mx-auto flex items-center justify-center shadow-ambient border border-surface-variant/50 relative">
              <Sprout className="w-8 h-8 text-primary" />
              <div className="absolute -bottom-0.5 -right-0.5 w-5 h-5 rounded-full bg-secondary-container flex items-center justify-center">
                <CheckCircle2 className="w-3 h-3 text-secondary" />
              </div>
            </div>
            <h1 className="text-2xl font-bold text-primary tracking-tight">Welcome back</h1>
            <p className="text-sm text-on-surface-variant">Sign in with your mobile number</p>
          </div>

          <LoginForm />
        </div>
      </main>
    </MarketingPage>
  );
}
