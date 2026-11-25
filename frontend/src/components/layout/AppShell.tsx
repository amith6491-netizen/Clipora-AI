import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  Cpu,
  Download,
  Film,
  LayoutDashboard,
  LayoutGrid,
  LogOut,
  Menu,
  Sparkles,
  UploadCloud,
  X,
} from "lucide-react";
import { api } from "../../api/client";
import { useAuth } from "../../context/AuthContext";
import type { SystemHealth } from "../../types";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    let active = true;
    api
      .getHealth()
      .then((res) => {
        if (active) setHealth(res);
      })
      .catch(() => {
        if (active) setHealth(null);
      });
    return () => {
      active = false;
    };
  }, [location.pathname]);

  const navItems = [
    {
      to: "/dashboard",
      label: "Dashboard",
      icon: LayoutDashboard,
      matches: (p: string) => p === "/dashboard",
    },
    {
      to: "/upload",
      label: "Upload / YouTube",
      icon: UploadCloud,
      matches: (p: string) => p === "/upload",
    },
    {
      to: "/processing",
      label: "AI Analysis Process",
      icon: Cpu,
      matches: (p: string) => p === "/processing" || p.endsWith("/processing"),
    },
    {
      to: "/gallery",
      label: "Generated Shorts Gallery",
      icon: LayoutGrid,
      matches: (p: string) => p === "/gallery" || p.endsWith("/shorts") || p.endsWith("/edit"),
    },
    {
      to: "/downloads",
      label: "Download Manager",
      icon: Download,
      matches: (p: string) => p === "/downloads",
    },
  ];

  const linkClass = (active: boolean) =>
    `flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-colors ${
      active
        ? "bg-violet-500/20 text-violet-200 border border-violet-500/30"
        : "text-slate-400 hover:bg-white/5 hover:text-slate-100 border border-transparent"
    }`;

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <div className="min-h-screen bg-[#07090f] text-slate-100 flex flex-col lg:flex-row">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex lg:w-64 lg:flex-col lg:fixed lg:inset-y-0 border-r border-white/10 bg-[#0b0f19]/95 backdrop-blur-xl">
        <div className="flex h-16 items-center gap-2.5 px-6 border-b border-white/10">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-cyan-500 shadow-lg shadow-violet-600/25">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <div>
              <span className="text-base font-bold tracking-tight text-white">Clipora AI</span>
              <span className="block text-[10px] font-medium uppercase tracking-wider text-violet-400">
                Shorts Studio
              </span>
            </div>
          </Link>
        </div>

        <nav className="flex-1 space-y-1.5 px-3 py-5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.matches(location.pathname);
            return (
              <Link key={item.to} to={item.to} className={linkClass(active)}>
                <Icon className="h-4 w-4 shrink-0" />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
          <Link
            to="/"
            className="flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-slate-400 hover:bg-white/5 hover:text-slate-100"
          >
            <Film className="h-4 w-4 shrink-0" />
            <span>Landing Overview</span>
          </Link>
        </nav>

        <div className="border-t border-white/10 p-4 space-y-3">
          <div className="rounded-xl border border-white/10 bg-[#111726] p-3">
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-1.5 font-medium text-slate-300">
                <Activity className="h-3.5 w-3.5 text-cyan-400" />
                Pipeline Engine
              </span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  health?.status === "ok"
                    ? "bg-emerald-500/15 text-emerald-300"
                    : "bg-amber-500/15 text-amber-300"
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    health?.status === "ok" ? "bg-emerald-400" : "bg-amber-400"
                  }`}
                />
                {health ? (health.status === "ok" ? "Online" : "Partial") : "Offline"}
              </span>
            </div>
            {health && (
              <div className="mt-2.5 grid grid-cols-2 gap-1.5 text-[11px] text-slate-400">
                <span className={health.mongodb_connected ? "text-emerald-300" : "text-rose-400"}>
                  ● MongoDB
                </span>
                <span className={health.ffmpeg_available ? "text-emerald-300" : "text-rose-400"}>
                  ● FFmpeg
                </span>
                <span className={health.faster_whisper_available ? "text-emerald-300" : "text-rose-400"}>
                  ● Whisper
                </span>
                <span className={health.yt_dlp_available ? "text-emerald-300" : "text-rose-400"}>
                  ● YouTube
                </span>
              </div>
            )}
          </div>

          {user && (
            <div className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-[#111726] px-3 py-2.5">
              <div className="min-w-0">
                <div className="truncate text-xs font-semibold text-white">{user.name}</div>
                <div className="truncate text-[11px] text-slate-400">{user.email}</div>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-500/15 hover:text-rose-300"
                title="Sign out"
                aria-label="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Mobile Topbar */}
      <header className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-white/10 bg-[#0b0f19]/90 px-4 backdrop-blur-xl lg:hidden">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-cyan-500">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <span className="font-bold text-white">Clipora AI</span>
        </Link>
        <button
          type="button"
          onClick={() => setMobileOpen((prev) => !prev)}
          className="rounded-lg border border-white/10 p-2 text-slate-300 hover:bg-white/5"
          aria-label="Toggle navigation"
        >
          {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </header>

      {mobileOpen && (
        <div className="border-b border-white/10 bg-[#0b0f19] px-4 py-3 space-y-1 lg:hidden">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = item.matches(location.pathname);
            return (
              <Link key={item.to} to={item.to} className={linkClass(active)}>
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
          {user && (
            <button
              type="button"
              onClick={handleLogout}
              className="flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium text-rose-300 hover:bg-rose-500/10"
            >
              <LogOut className="h-4 w-4" />
              <span>Sign Out ({user.email})</span>
            </button>
          )}
        </div>
      )}

      {/* Main Content */}
      <main className="flex-1 lg:pl-64">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}
