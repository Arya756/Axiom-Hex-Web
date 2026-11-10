import React from "react";
import { UserRole } from "../../types";
import { Shield, Sparkles, UserCheck, Layers, BookOpen, Compass, CheckSquare } from "lucide-react";

interface NavbarProps {
  currentRole: UserRole;
  onRoleChange: (role: UserRole) => void;
  activeTab: "workspace" | "admin" | "reviewer";
  onTabChange: (tab: "workspace" | "admin" | "reviewer") => void;
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
    <header className="sticky top-0 z-40 bg-white/95 backdrop-blur-sm border-b border-pastel-border shadow-pastel">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
        {/* Brand & Tenant Logo */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-pastel-indigo-badge via-pastel-blue-badge to-pastel-purple-badge border border-pastel-indigo-border flex items-center justify-center shadow-pastel">
            <Sparkles className="w-5 h-5 text-pastel-indigo-text" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-sm tracking-tight text-pastel-text">Axiom</span>
              <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-pastel-bg text-pastel-subtext border border-pastel-border">
                Round 2
              </span>
            </div>
            <p className="text-[11px] text-pastel-muted">
              Tenant: <span className="font-semibold text-pastel-indigo-text">Meridian Flow</span> (RLS Isolated)
            </p>
          </div>
        </div>

        {/* View Tabs */}
        <nav className="flex items-center gap-1.5 bg-pastel-bg p-1 rounded-xl border border-pastel-border" aria-label="Main Navigation">
          <button
            type="button"
            onClick={() => onTabChange("workspace")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === "workspace"
                ? "bg-white text-pastel-indigo-text shadow-pastel border border-pastel-border"
                : "text-pastel-subtext hover:text-pastel-text"
            }`}
          >
            <Compass className="w-3.5 h-3.5" />
            Creator Workspace
          </button>

          <button
            type="button"
            onClick={() => onTabChange("reviewer")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === "reviewer"
                ? "bg-white text-pastel-indigo-text shadow-pastel border border-pastel-border"
                : "text-pastel-subtext hover:text-pastel-text"
            }`}
          >
            <CheckSquare className="w-3.5 h-3.5" />
            Review Queue
          </button>

          <button
            type="button"
            onClick={() => onTabChange("admin")}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
              activeTab === "admin"
                ? "bg-white text-pastel-indigo-text shadow-pastel border border-pastel-border"
                : "text-pastel-subtext hover:text-pastel-text"
            }`}
          >
            <BookOpen className="w-3.5 h-3.5" />
            Admin Brand Kit
          </button>
        </nav>

        {/* Role Persona Switcher (Judge friendly) */}
        <div className="flex items-center gap-2">
          <label htmlFor="role-select" className="text-xs font-medium text-pastel-subtext hidden md:block">
            Active Role:
          </label>
          <select
            id="role-select"
            value={currentRole}
            onChange={(e) => onRoleChange(e.target.value as UserRole)}
            className="text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-pastel-indigo-border bg-pastel-indigo-bg text-pastel-indigo-text shadow-pastel cursor-pointer focus:ring-2 focus:ring-pastel-indigo-border outline-none"
          >
            {roles.map((r) => (
              <option key={r.role} value={r.role}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
      </div>
    </header>
  );
}

