import { useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, Lock, Mail, Sparkles, User as UserIcon } from "lucide-react";
import { ErrorBanner } from "../components/common/ErrorBanner";
import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTarget = (location.state as { from?: string } | null)?.from || "/dashboard";

  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) {
    return <Navigate to={redirectTarget} replace />;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (mode === "register" && name.trim().length < 2) {
      setError("Please enter your full name (at least 2 characters).");
      return;
    }
    if (!email.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }
    if (mode === "register" && password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setSubmitting(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(name.trim(), email, password);
      }
      navigate(redirectTarget, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#07090f] text-slate-100 flex flex-col justify-center px-4 py-12 relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_rgba(124,58,237,0.20),_transparent_55%)]" />

      <div className="relative mx-auto w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <Link to="/" className="inline-flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 shadow-lg shadow-violet-600/25">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold tracking-tight text-white">Clipora AI</span>
          </Link>
          <h1 className="text-2xl font-bold text-white">
            {mode === "login" ? "Welcome back" : "Create your studio account"}
          </h1>
          <p className="text-sm text-slate-400">
            {mode === "login"
              ? "Sign in to manage videos, AI shorts, and HD exports."
              : "Start turning long videos and YouTube links into viral shorts."}
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-[#0d121f]/95 p-6 shadow-2xl shadow-black/50 space-y-5">
          {/* Mode Tabs */}
          <div className="grid grid-cols-2 rounded-xl border border-white/10 bg-[#080b13] p-1">
            <button
              type="button"
              onClick={() => {
                setMode("login");
                setError(null);
              }}
              className={`rounded-lg py-2 text-xs font-semibold transition-colors ${
                mode === "login" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => {
                setMode("register");
                setError(null);
              }}
              className={`rounded-lg py-2 text-xs font-semibold transition-colors ${
                mode === "register" ? "bg-violet-600 text-white" : "text-slate-400 hover:text-white"
              }`}
            >
              Create Account
            </button>
          </div>

          <ErrorBanner message={error} onDismiss={() => setError(null)} />

          <form onSubmit={handleSubmit} className="space-y-4">
            {mode === "register" && (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-300">Full Name</label>
                <div className="relative">
                  <UserIcon className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Alex Morgan"
                    className="w-full rounded-xl border border-white/10 bg-[#121829] py-2 pl-9 pr-3 text-sm text-white placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
                  />
                </div>
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Email Address</label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-white/10 bg-[#121829] py-2 pl-9 pr-3 text-sm text-white placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-300">Password</label>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
                <input
                  type={showPassword ? "text" : "password"}
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={mode === "register" ? "At least 6 characters" : "Enter your password"}
                  className="w-full rounded-xl border border-white/10 bg-[#121829] py-2 pl-9 pr-10 text-sm text-white placeholder:text-slate-500 focus:border-violet-500 focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((prev) => !prev)}
                  className="absolute right-2.5 top-2 rounded-md p-0.5 text-slate-400 hover:text-white"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 py-2.5 text-sm font-semibold text-white shadow-lg shadow-violet-600/25 hover:opacity-95 disabled:opacity-50"
            >
              {submitting
                ? mode === "login"
                  ? "Signing in…"
                  : "Creating account…"
                : mode === "login"
                ? "Sign In"
                : "Create Studio Account"}
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-slate-500">
          <Link to="/" className="text-slate-400 hover:text-white underline underline-offset-4">
            Back to Clipora AI overview
          </Link>
        </p>
      </div>
    </div>
  );
}
