import React from "react";
import { ShieldCheck } from "lucide-react";

export function AxeDisclosure() {
  return (
    <div
      role="region"
      aria-label="Accessibility compliance disclosure"
      className="rounded-xl border border-indigo-200/90 bg-indigo-50/70 px-4 py-3 text-xs text-indigo-950 flex items-start sm:items-center gap-3 shadow-2xs"
    >
      <div className="p-1 rounded-lg bg-indigo-100 text-indigo-700 flex-shrink-0">
        <ShieldCheck className="w-4 h-4" aria-hidden="true" />
      </div>
      <div className="flex-1 leading-relaxed">
        <span className="font-bold text-slate-900 mr-1.5">WCAG 2.2 AA Partial Coverage Disclosure:</span>
        <span className="text-slate-700">
          In keeping with PRD §5.4, automated <code className="font-mono bg-white px-1.5 py-0.5 rounded border border-indigo-200 text-indigo-900 font-semibold">axe-core</code> test results represent verified partial coverage (contrast, ARIA roles, focus visibility, keyboard tree) rather than full formal legal certification.
        </span>
      </div>
    </div>
  );
}
