import React, { useState } from "react";
import { Finding, FindingDecision } from "../../types";
import { diffWords } from "diff";
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Sparkles,
  ShieldAlert,
  GitBranch,
  Bot,
  HelpCircle,
  MessageSquare,
  FileCheck,
} from "lucide-react";

interface FindingCardProps {
  finding: Finding;
  isSelected?: boolean;
  onSelect?: (finding: Finding) => void;
  onDecision?: (findingId: string, decision: FindingDecision, reason?: string) => void;
  onEditFix?: (findingId: string, editedText: string) => void;
}

export function FindingCard({
  finding,
  isSelected,
  onSelect,
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

  const severityColors = {
    critical: "bg-pastel-rose-badge text-pastel-rose-text border-pastel-rose-border",
    high: "bg-pastel-rose-badge text-pastel-rose-text border-pastel-rose-border",
    medium: "bg-pastel-amber-badge text-pastel-amber-text border-pastel-amber-border",
    low: "bg-pastel-blue-badge text-pastel-blue-text border-pastel-blue-border",
  };

  return (
    <article
      tabIndex={0}
      role="region"
      aria-label={`Finding ${finding.finding_id}: ${finding.type}`}
      onClick={() => onSelect && onSelect(finding)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect && onSelect(finding);
        }
      }}
      className={`rounded-xl border transition-all p-4 space-y-3 cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-pastel-indigo-border ${
        isSelected
          ? "border-pastel-indigo-border bg-pastel-indigo-bg/40 shadow-pastel-md ring-2 ring-pastel-indigo-border"
          : "border-pastel-border bg-pastel-card hover:border-pastel-indigo-border/60 hover:bg-pastel-hover/50 shadow-pastel"
      }`}
    >
      {/* 1. Header Badges: Type, Severity, Confidence, Method, Assisted */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span
            className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full border ${
              severityColors[finding.severity]
            }`}
          >
            {finding.type} ({finding.severity})
          </span>

          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-pastel-bg text-pastel-subtext border border-pastel-border">
            {Math.round(finding.confidence * 100)}% conf
          </span>

          <span className="text-[10px] px-2 py-0.5 rounded-full bg-pastel-indigo-badge text-pastel-indigo-text border border-pastel-indigo-border capitalize">
            {finding.disclosure.method.replace("_", " ")}
          </span>

          {finding.disclosure.assisted && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-pastel-purple-badge text-pastel-purple-text border border-pastel-purple-border flex items-center gap-1">
              <Bot className="w-3 h-3" />
              Assisted
            </span>
          )}
        </div>

        <div className="flex items-center gap-1 text-[11px] font-mono text-pastel-muted">
          <span>{finding.span.unit_id}</span>
          <span>[{finding.span.start}:{finding.span.end}]</span>
        </div>
      </div>

      {/* 2. Quoted Target Span */}
      <div className="p-2.5 rounded-lg bg-pastel-bg border border-pastel-border text-xs">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-pastel-muted mb-1">
          Identified Span:
        </div>
        <div className="font-mono text-pastel-text bg-white px-2 py-1 rounded border border-pastel-border inline-block">
          &ldquo;{finding.span.quote}&rdquo;
        </div>
      </div>

      {/* 3. Evidence-First Layout: Verified receipts & citations shown BEFORE explanation */}
      <div className="rounded-lg border border-pastel-border bg-white p-3 space-y-2 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-bold uppercase tracking-wider text-pastel-indigo-text flex items-center gap-1">
            <FileCheck className="w-3.5 h-3.5" />
            Verified Evidence & Citation Receipt
          </span>
          <span className="text-[10px] text-pastel-muted">Citation Verifier Passed</span>
        </div>

        {finding.evidence.map((ev, idx) => (
          <div key={idx} className="space-y-1.5 p-2 rounded bg-pastel-bg/60 border border-pastel-border">
            <div className="flex items-center justify-between text-xs">
              <span className="font-semibold text-pastel-text">
                Source: <span className="font-mono text-pastel-indigo-text font-bold">{ev.source}</span>
                {ev.version ? `@v${ev.version}` : ""}
              </span>
              <span
                className={`text-[10px] font-medium px-1.5 py-0.2 rounded capitalize ${
                  ev.status === "superseded"
                    ? "bg-pastel-rose-badge text-pastel-rose-text"
                    : "bg-pastel-green-badge text-pastel-green-text"
                }`}
              >
                {ev.status}
              </span>
            </div>

            {ev.current_value && (
              <div className="text-xs text-pastel-subtext flex items-center gap-1.5 flex-wrap">
                <span className="font-medium text-pastel-text">Current Standard:</span>
                <span className="font-mono bg-pastel-green-bg text-pastel-green-text px-1.5 py-0.5 rounded border border-pastel-green-border font-semibold">
                  {ev.current_value}
                </span>
                {ev.current_version && <span className="text-[11px] text-pastel-muted">(v{ev.current_version})</span>}
              </div>
            )}

            {ev.trace && (
              <p className="text-[11px] text-pastel-muted italic font-mono pt-0.5 border-t border-pastel-border/60">
                Trace: {ev.trace}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* 4. Verdict & Explanation */}
      <div className="space-y-1">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-pastel-muted">
          Verdict & Explanation:
        </div>
        <p className="text-xs text-pastel-text leading-relaxed">{finding.explanation}</p>
      </div>

      {/* 5. Tracked-Change Fix Diff (jsdiff) */}
      {finding.suggested_fix && (
        <div className="rounded-lg border border-pastel-indigo-border bg-pastel-indigo-bg/30 p-3 space-y-2 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-pastel-indigo-text flex items-center gap-1">
              <Sparkles className="w-3.5 h-3.5" />
              Suggested Tracked-Change Fix
            </span>
            {finding.suggested_fix.intent_similarity && (
              <span className="text-[10px] text-pastel-indigo-text font-mono font-medium">
                Intent similarity: {Math.round(finding.suggested_fix.intent_similarity * 100)}%
              </span>
            )}
          </div>

          {/* Inline Diff View */}
          <div className="p-2 rounded bg-white border border-pastel-border font-mono text-xs leading-relaxed flex flex-wrap gap-1 items-center">
            {diffParts.map((part, index) => {
              if (part.added) {
                return (
                  <span
                    key={index}
                    className="bg-pastel-green-badge text-pastel-green-text border border-pastel-green-border px-1 rounded font-semibold"
                  >
                    +{part.value}
                  </span>
                );
              }
              if (part.removed) {
                return (
                  <span
                    key={index}
                    className="bg-pastel-rose-badge text-pastel-rose-text border border-pastel-rose-border px-1 rounded line-through opacity-80"
                  >
                    -{part.value}
                  </span>
                );
              }
              return (
                <span key={index} className="text-pastel-text">
                  {part.value}
                </span>
              );
            })}
          </div>

          {isEditingFix && (
            <form onSubmit={handleSaveCustomFix} className="pt-2 space-y-2">
              <label htmlFor={`edit-fix-${finding.finding_id}`} className="block text-[11px] font-semibold text-pastel-text">
                Custom Edit Text (Re-checks intent constraints):
              </label>
              <input
                id={`edit-fix-${finding.finding_id}`}
                type="text"
                value={customFixText}
                onChange={(e) => setCustomFixText(e.target.value)}
                className="w-full text-xs px-2.5 py-1.5 rounded-lg border border-pastel-border bg-white text-pastel-text"
              />
              <div className="flex gap-2 justify-end">
                <button
                  type="button"
                  onClick={() => setIsEditingFix(false)}
                  className="px-2.5 py-1 text-xs text-pastel-subtext hover:bg-pastel-hover rounded"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3 py-1 text-xs font-semibold bg-pastel-indigo-badge text-pastel-indigo-text rounded border border-pastel-indigo-border"
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
        <form onSubmit={handleDisputeSubmit} className="p-3 rounded-lg bg-pastel-rose-bg border border-pastel-rose-border space-y-2">
          <label htmlFor={`dispute-reason-${finding.finding_id}`} className="block text-xs font-semibold text-pastel-rose-text">
            Mandatory Dispute Reason *
          </label>
          <textarea
            id={`dispute-reason-${finding.finding_id}`}
            rows={2}
            value={disputeReason}
            onChange={(e) => setDisputeReason(e.target.value)}
            placeholder="Explain why this finding is inaccurate, out of context, or should be overridden."
            required
            className="w-full text-xs p-2 rounded border border-pastel-rose-border bg-white text-pastel-text placeholder:text-pastel-muted"
          />
          {disputeError && <p className="text-[11px] text-pastel-rose-text">{disputeError}</p>}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsDisputing(false)}
              className="px-2.5 py-1 text-xs text-pastel-subtext hover:bg-pastel-hover rounded"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-3 py-1 text-xs font-semibold bg-pastel-rose-badge text-pastel-rose-text rounded border border-pastel-rose-border"
            >
              Submit Dispute
            </button>
          </div>
        </form>
      )}

      {/* 7. Action Buttons */}
      <div className="flex items-center justify-between pt-1 border-t border-pastel-border/60">
        <div className="text-[11px] text-pastel-muted flex items-center gap-1">
          <span>Route:</span>
          <span className="font-semibold text-pastel-text capitalize">{finding.route_to}</span>
        </div>

        <div className="flex items-center gap-2">
          {finding.suggested_fix && !isEditingFix && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsEditingFix(true);
              }}
              className="px-2.5 py-1 text-xs font-medium text-pastel-subtext hover:bg-pastel-hover rounded border border-pastel-border"
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
              className="px-2.5 py-1 text-xs font-medium text-pastel-rose-text hover:bg-pastel-rose-bg rounded border border-pastel-rose-border"
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
            className="px-3 py-1 text-xs font-semibold bg-pastel-green-badge hover:bg-pastel-green-border text-pastel-green-text rounded border border-pastel-green-border shadow-pastel flex items-center gap-1"
          >
            <CheckCircle className="w-3.5 h-3.5" />
            Accept Fix
          </button>
        </div>
      </div>
    </article>
  );
}

