import React from "react";
import { UserRole } from "../../types";
import { Sparkles, Compass, CheckSquare, BookOpen, ShieldCheck, Radar, BarChart3 } from "lucide-react";

export type AppTab = "workspace" | "admin" | "reviewer" | "radar" | "insights";

interface NavbarProps {
  currentRole: UserRole;
  onRoleChange: (role: UserRole) => void;
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
}

export function Navbar({
  currentRole,
  onRoleChange,
  activeTab,
  onTabChange,
}: NavbarProps) {
  const roles: { role: UserRole; label: string; desc: string }[] = [
    { role: "creator", label: "Creator", desc: "Upload drafts & resolve findings" },
    { role: "reviewer", label: "Reviewer", desc: "Editorial & brand review" },
    { role: "legal_reviewer", label: "Legal Reviewer", desc: "Mandatory claims sign-off" },
    { role: "admin", label: "Admin", desc: "Brand kit & source compiler" },
  ];

  return (
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand & Tenant Logo */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-md shadow-indigo-100 ring-1 ring-black/5">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base tracking-tight text-slate-900">Axiom</span>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-100">
                Round 2
              </span>
            </div>
            <p className="text-xs text-slate-500 flex items-center gap-1 font-normal">
              Tenant: <span className="font-semibold text-slate-700">Meridian Flow</span>
              <span className="inline-flex items-center text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200">
                RLS Isolated
              </span>
            </p>
          </div>
        </div>

        {/* View Tabs */}
        <nav className="flex items-center gap-1 bg-slate-100/80 p-1 rounded-xl border border-slate-200/80 shadow-inner" aria-label="Main Navigation">
          <button
            type="button"
            onClick={() => onTabChange("workspace")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all duration-150 ${
              activeTab === "workspace"
                ? "bg-white text-indigo-600 shadow-sm border border-slate-200/60"
                : "text-slate-600 hover:text-slate-900 hover:bg-white/50"
            }`}
          >
            <Compass className="w-3.5 h-3.5 text-indigo-500" />
            Creator Workspace
          </button>

          <button
            type="button"
            onClick={() => onTabChange("reviewer")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all duration-150 ${
              activeTab === "reviewer"
                ? "bg-white text-indigo-600 shadow-sm border border-slate-200/60"
                : "text-slate-600 hover:text-slate-900 hover:bg-white/50"
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5 text-indigo-500" />
            Review Queue
          </button>

          <button
            type="button"
            onClick={() => onTabChange("admin")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all duration-150 ${
              activeTab === "admin"
                ? "bg-white text-indigo-600 shadow-sm border border-slate-200/60"
                : "text-slate-600 hover:text-slate-900 hover:bg-white/50"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5 text-indigo-500" />
            Admin Brand Kit
          </button>

          <button
            type="button"
            onClick={() => onTabChange("radar")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all duration-150 ${
              activeTab === "radar"
                ? "bg-white text-indigo-600 shadow-sm border border-slate-200/60"
                : "text-slate-600 hover:text-slate-900 hover:bg-white/50"
            }`}
          >
            <Radar className="w-3.5 h-3.5 text-purple-500" />
            Ambiguity Radar
          </button>

          <button
            type="button"
            onClick={() => onTabChange("insights")}
            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all duration-150 ${
              activeTab === "insights"
                ? "bg-white text-indigo-600 shadow-sm border border-slate-200/60"
                : "text-slate-600 hover:text-slate-900 hover:bg-white/50"
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5 text-indigo-500" />
            Recurring Insights
          </button>
        </nav>

        {/* Role Persona Switcher (Judge friendly) */}
        <div className="flex items-center gap-2.5">
          <label htmlFor="role-select" className="text-xs font-medium text-slate-500 hidden md:block">
            Active Role:
          </label>
          <div className="relative">
            <select
              id="role-select"
              value={currentRole}
              onChange={(e) => onRoleChange(e.target.value as UserRole)}
              className="text-xs font-semibold pl-3 pr-8 py-1.5 rounded-lg border border-slate-300 bg-white text-slate-800 shadow-sm cursor-pointer hover:border-indigo-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none transition-all appearance-none"
            >
              {roles.map((r) => (
                <option key={r.role} value={r.role}>
                  {r.label}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-400">
              <svg className="w-3.5 h-3.5 fill-current" viewBox="0 0 20 20">
                <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
              </svg>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
}
