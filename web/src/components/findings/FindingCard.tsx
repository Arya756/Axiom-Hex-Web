import React, { useState } from "react";
import { Finding, FindingDecision } from "../../types";
import { diffWords } from "diff";
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Sparkles,
  Bot,
  FileCheck,
} from "lucide-react";

interface FindingCardProps {
  finding: Finding;
  isSelected?: boolean;
  onSelect?: (finding: Finding) => void;
  onNavigate?: (direction: "next" | "prev") => void;
  onDecision?: (findingId: string, decision: FindingDecision, reason?: string) => void;
  onEditFix?: (findingId: string, editedText: string) => void;
}

export function FindingCard({
  finding,
  isSelected,
  onSelect,
  onNavigate,
  onDecision,
  onEditFix,
}: FindingCardProps) {
  const [isDisputing, setIsDisputing] = useState(false);
  const [disputeReason, setDisputeReason] = useState("");
  const [disputeError, setDisputeError] = useState("");
  const [isEditingFix, setIsEditingFix] = useState(false);
  const [customFixText, setCustomFixText] = useState(finding.suggested_fix?.text || "");

  const handleDisputeSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!disputeReason.trim()) {
      setDisputeError("A written reason is required to dispute this finding.");
      return;
    }
    setDisputeError("");
    if (onDecision) {
      onDecision(finding.finding_id, "dispute", disputeReason.trim());
    }
    setIsDisputing(false);
  };

  const handleAccept = () => {
    if (onDecision) {
      onDecision(finding.finding_id, "accept");
    }
  };

  const handleSaveCustomFix = (e: React.FormEvent) => {
    e.preventDefault();
    if (onEditFix) {
      onEditFix(finding.finding_id, customFixText);
    }
    setIsEditingFix(false);
  };

  // Compute tracked changes diff using jsdiff
  const quoteText = finding.span.quote;
  const fixText = finding.suggested_fix?.text || "";
  const diffParts = fixText ? diffWords(quoteText, fixText) : [];

  const severityBadgeStyles: Record<string, string> = {
    critical: "bg-rose-50 text-rose-700 border-rose-200 font-bold",
    high: "bg-rose-50 text-rose-700 border-rose-200 font-bold",
    medium: "bg-amber-50 text-amber-800 border-amber-200 font-semibold",
    low: "bg-sky-50 text-sky-800 border-sky-200 font-medium",
  };

  return (
    <article
      tabIndex={0}
      role="region"
      data-finding-id={finding.finding_id}
      aria-label={`Finding ${finding.finding_id}: ${finding.type}`}
      aria-current={isSelected ? "true" : undefined}
      onClick={() => onSelect && onSelect(finding)}
      onKeyDown={(e) => {
        if (e.target !== e.currentTarget) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect && onSelect(finding);
        } else if (e.key === "ArrowDown") {
          e.preventDefault();
          onNavigate && onNavigate("next");
        } else if (e.key === "ArrowUp") {
          e.preventDefault();
          onNavigate && onNavigate("prev");
        }
      }}
      className={`rounded-2xl border transition-all duration-150 p-4 sm:p-5 space-y-3.5 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
        isSelected
          ? "border-indigo-500 bg-white ring-2 ring-indigo-500/20 shadow-md"
          : "border-slate-200/90 bg-white hover:border-slate-300 hover:shadow-sm shadow-sm"
      }`}
    >
      {/* 1. Header Badges: Type, Severity, Confidence, Method, Assisted */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className={`text-xs uppercase px-2.5 py-0.5 rounded-full border ${
              severityBadgeStyles[finding.severity] || "bg-slate-100 text-slate-700 border-slate-200"
            }`}
          >
            {finding.type} ({finding.severity})
          </span>

          <span className="text-xs font-mono font-medium px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
            {Math.round(finding.confidence * 100)}% conf
          </span>

          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200 capitalize">
            {finding.disclosure.method.replace("_", " ")}
          </span>

          {finding.disclosure.assisted && (
            <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 flex items-center gap-1">
              <Bot className="w-3.5 h-3.5" />
              Assisted
            </span>
          )}
        </div>

        <div className="flex items-center gap-1.5 text-xs font-mono text-slate-500">
          <span className="bg-slate-100 px-1.5 py-0.5 rounded text-slate-600 font-medium">{finding.span.unit_id}</span>
          <span>[{finding.span.start}:{finding.span.end}]</span>
        </div>
      </div>

      {/* 2. Quoted Target Span */}
      <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 text-xs flex items-center gap-2 flex-wrap">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 flex-shrink-0">
          Identified Span:
        </span>
        <code className="font-mono text-slate-900 bg-white px-2.5 py-1 rounded-lg border border-slate-200 font-semibold shadow-2xs">
          &ldquo;{finding.span.quote}&rdquo;
        </code>
      </div>

      {/* 3. Evidence-First Layout: Verified receipts & citations shown BEFORE explanation */}
      <div className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-2.5 text-xs shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <span className="text-xs font-bold uppercase tracking-wider text-indigo-700 flex items-center gap-1.5">
            <FileCheck className="w-4 h-4 text-indigo-600" />
            Verified Evidence & Citation Receipt
          </span>
          <span className="text-[11px] font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
            Citation Verifier Passed
          </span>
        </div>

        {finding.evidence.map((ev, idx) => (
          <div key={idx} className="space-y-1.5 p-2.5 rounded-lg bg-slate-50/80 border border-slate-200/80">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-slate-800">
                Source: <span className="font-mono text-indigo-700 font-bold bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200/60">{ev.source}</span>
                {ev.version ? <span className="text-slate-500 ml-1">@v{ev.version}</span> : ""}
              </span>
              <span
                className={`text-[11px] font-bold px-2 py-0.5 rounded-full border capitalize ${
                  ev.status === "superseded"
                    ? "bg-rose-50 text-rose-700 border-rose-200"
                    : "bg-emerald-50 text-emerald-700 border-emerald-200"
                }`}
              >
                {ev.status}
              </span>
            </div>

            {ev.current_value && (
              <div className="text-xs text-slate-700 flex items-center gap-2 flex-wrap pt-0.5">
                <span className="font-medium text-slate-600">Current Standard:</span>
                <span className="font-mono bg-emerald-50 text-emerald-800 px-2 py-0.5 rounded border border-emerald-200 font-bold">
                  {ev.current_value}
                </span>
                {ev.current_version && <span className="text-[11px] text-slate-500 font-medium">(v{ev.current_version})</span>}
              </div>
            )}

            {ev.trace && (
              <p className="text-[11px] text-slate-500 italic font-mono pt-1 border-t border-slate-200/60">
                Trace: {ev.trace}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* 4. Verdict & Explanation */}
      <div className="space-y-1">
        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
          Verdict & Explanation:
        </div>
        <p className="text-xs text-slate-700 leading-relaxed font-normal">{finding.explanation}</p>
      </div>

      {/* 5. Tracked-Change Fix Diff (jsdiff) - Clean inline flow without jagged word cutoffs */}
      {finding.suggested_fix && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50/40 p-3.5 space-y-2.5 text-xs">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <span className="text-xs font-bold uppercase tracking-wider text-indigo-900 flex items-center gap-1.5">
              <Sparkles className="w-4 h-4 text-indigo-600" />
              Suggested Tracked-Change Fix
            </span>
            <div className="flex items-center gap-1.5 flex-wrap">
              {(finding.disclosure.assisted || finding.disclosure.method === "llm_assisted") && (
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 flex items-center gap-1">
                  <Bot className="w-3 h-3" aria-hidden="true" />
                  Assisted Fix
                </span>
              )}
              {finding.suggested_fix.intent_similarity && (
                <span className="text-xs text-indigo-800 font-mono font-semibold bg-indigo-100/80 px-2 py-0.5 rounded border border-indigo-200">
                  Intent similarity: {Math.round(finding.suggested_fix.intent_similarity * 100)}%
                </span>
              )}
            </div>
          </div>

          {/* Natural inline diff layout */}
          <div className="p-3 rounded-lg bg-white border border-indigo-100 font-mono text-xs leading-relaxed shadow-inner">
            {diffParts.map((part, index) => {
              if (part.added) {
                return (
                  <ins
                    key={index}
                    className="bg-emerald-100 text-emerald-900 border border-emerald-300 px-1.5 py-0.5 rounded font-bold no-underline inline-block mx-0.5"
                  >
                    +{part.value}
                  </ins>
                );
              }
              if (part.removed) {
                return (
                  <del
                    key={index}
                    className="bg-rose-100 text-rose-900 border border-rose-300 px-1.5 py-0.5 rounded font-semibold line-through inline-block mx-0.5"
                  >
                    -{part.value}
                  </del>
                );
              }
              return (
                <span key={index} className="text-slate-800">
                  {part.value}
                </span>
              );
            })}
          </div>

          {isEditingFix && (
            <form onSubmit={handleSaveCustomFix} className="pt-2 space-y-2 border-t border-indigo-100">
              <label htmlFor={`edit-fix-${finding.finding_id}`} className="block text-xs font-semibold text-slate-800">
                Custom Edit Text (Re-checks intent constraints):
              </label>
              <input
                id={`edit-fix-${finding.finding_id}`}
                type="text"
                value={customFixText}
                onChange={(e) => setCustomFixText(e.target.value)}
                className="w-full text-xs px-3 py-2 rounded-lg border border-slate-300 bg-white text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setIsEditingFix(false)}
                  className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-lg shadow-sm shadow-indigo-200 transition-colors"
                >
                  Save & Re-check
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* 6. Dispute Form (Enforces written reason) */}
      {isDisputing && (
        <form onSubmit={handleDisputeSubmit} className="p-3.5 rounded-xl bg-rose-50/70 border border-rose-200 space-y-2.5">
          <label htmlFor={`dispute-reason-${finding.finding_id}`} className="block text-xs font-bold text-rose-900">
            Mandatory Dispute Reason *
          </label>
          <textarea
            id={`dispute-reason-${finding.finding_id}`}
            rows={2}
            value={disputeReason}
            onChange={(e) => setDisputeReason(e.target.value)}
            placeholder="Explain why this finding is inaccurate, out of context, or should be overridden."
            required
            className="w-full text-xs p-2.5 rounded-lg border border-rose-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-rose-500 focus:ring-2 focus:ring-rose-100 outline-none shadow-sm"
          />
          {disputeError && <p className="text-xs font-semibold text-rose-700">{disputeError}</p>}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsDisputing(false)}
              className="px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-white rounded-lg border border-slate-200 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-3.5 py-1.5 text-xs font-semibold bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white rounded-lg shadow-sm shadow-rose-200 transition-colors"
            >
              Submit Dispute
            </button>
          </div>
        </form>
      )}

      {/* 7. Action Buttons */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-100">
        <div className="text-xs text-slate-500 flex items-center gap-1.5">
          <span>Route:</span>
          <span className="font-semibold text-slate-800 capitalize bg-slate-100 px-2 py-0.5 rounded border border-slate-200/60">
            {finding.route_to}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {finding.suggested_fix && !isEditingFix && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsEditingFix(true);
              }}
              className="px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white hover:bg-slate-50 rounded-lg border border-slate-300 shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1"
            >
              Edit Fix
            </button>
          )}

          {!isDisputing && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsDisputing(true);
              }}
              className="px-3 py-1.5 text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100/80 rounded-lg border border-rose-200 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-1"
            >
              Dispute
            </button>
          )}

          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              handleAccept();
            }}
            className="px-3.5 py-1.5 text-xs font-semibold bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white rounded-lg shadow-sm shadow-emerald-200 flex items-center gap-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-1"
          >
            <CheckCircle className="w-3.5 h-3.5" />
            Accept Fix
          </button>
        </div>
      </div>
    </article>
  );
}
