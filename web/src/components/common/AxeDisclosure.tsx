import React from "react";
import { ShieldCheck, Info } from "lucide-react";

export function AxeDisclosure() {
  return (
    <div
      role="region"
      aria-label="Accessibility compliance disclosure"
      className="rounded-lg border border-pastel-indigo-border bg-pastel-indigo-bg p-3 text-xs text-pastel-indigo-text flex items-start gap-2.5 shadow-pastel"
    >
      <ShieldCheck className="w-4 h-4 mt-0.5 text-pastel-indigo-text flex-shrink-0" aria-hidden="true" />
      <div className="space-y-0.5">
        <span className="font-semibold text-pastel-text">WCAG 2.2 AA Partial Coverage Disclosure:</span>
        <p className="text-pastel-subtext">
          In keeping with PRD §5.4, automated <code className="font-mono bg-white/70 px-1 py-0.5 rounded border border-pastel-border">axe-core</code> test results represent verified partial coverage (contrast, ARIA roles, focus visibility, keyboard tree) rather than full formal legal certification.
        </p>
      </div>
    </div>
  );
}

