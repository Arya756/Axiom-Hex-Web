import React, { useState } from "react";
import { Revision, Finding, UserRole } from "../../types";
import { diffWords } from "diff";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Scale,
  GitCompare,
  FileCheck2,
  Clock,
  ShieldCheck,
  Send,
} from "lucide-react";

interface ReviewerQueueProps {
  revisions: Revision[];
  findings: Finding[];
  currentUserRole: UserRole;
  onApproveRevision: (revisionId: string, contentHash: string) => void;
  onRequestChanges: (revisionId: string, notes: string) => void;
  onOverrideFinding: (findingId: string, reason: string) => void;
}

export function ReviewerQueue({
  revisions,
  findings,
  currentUserRole,
  onApproveRevision,
  onRequestChanges,
  onOverrideFinding,
}: ReviewerQueueProps) {
  const [selectedRevId, setSelectedRevId] = useState<string>(revisions[0]?.id || "");
  const [showDiff, setShowDiff] = useState(false);
  const [requestNotes, setRequestNotes] = useState("");
  const [isRequesting, setIsRequesting] = useState(false);
  const [overrideModal, setOverrideModal] = useState<{ findingId: string } | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [overrideError, setOverrideError] = useState("");

  const selectedRevision = revisions.find((r) => r.id === selectedRevId) || revisions[0];

  // Check if any claim-type findings exist (contradicted, outdated, unsupported)
  const claimFindings = findings.filter((f) =>
    ["contradicted", "outdated", "unsupported"].includes(f.type)
  );
  const hasClaimFindings = claimFindings.length > 0;
  const requiresLegalReviewer = hasClaimFindings;
  const canApprove =
    currentUserRole === "admin" ||
    (requiresLegalReviewer ? currentUserRole === "legal_reviewer" : currentUserRole === "reviewer");

  const handleApprove = () => {
    if (!selectedRevision) return;
    onApproveRevision(selectedRevision.id, selectedRevision.content_hash);
  };

  const handleRequestSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!requestNotes.trim()) return;
    onRequestChanges(selectedRevId, requestNotes.trim());
    setIsRequesting(false);
    setRequestNotes("");
  };

  const handleOverrideSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideReason.trim()) {
      setOverrideError("A written justification reason is mandatory to override this finding.");
      return;
    }
    setOverrideError("");
    if (overrideModal) {
      onOverrideFinding(overrideModal.findingId, overrideReason.trim());
    }
    setOverrideModal(null);
    setOverrideReason("");
  };

  // Simulated revision diff text
  const originalDraftText =
    "With MFP, enterprises achieve uncompromised compliance. Over 10,000+ customers rely on our infrastructure daily. Recognized as the #1 automated compliance platform, delivering 99.9% uptime.";
  const revisedDraftText =
    "With Meridian Flow Platform, enterprises achieve uncompromised compliance. Over 25,000+ customers rely on our infrastructure daily. Recognized as an industry-leading automated compliance platform, delivering 99.95% uptime.";
  const diffParts = diffWords(originalDraftText, revisedDraftText);

  return (
    <div className="space-y-4">
      {/* Revision Selection Header */}
      <div className="rounded-xl border border-pastel-border bg-pastel-card p-4 shadow-pastel space-y-3">
        <div className="flex items-center justify-between flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <Scale className="w-5 h-5 text-pastel-indigo-text" />
            <div>
              <h2 className="text-sm font-bold text-pastel-text">Governance & Review Queue</h2>
              <p className="text-xs text-pastel-muted">Role active: <span className="font-semibold capitalize text-pastel-indigo-text">{currentUserRole}</span></p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowDiff(!showDiff)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border flex items-center gap-1.5 transition-all ${
                showDiff
                  ? "bg-pastel-indigo-badge text-pastel-indigo-text border-pastel-indigo-border shadow-pastel"
                  : "bg-white text-pastel-subtext border-pastel-border hover:bg-pastel-hover"
              }`}
            >
              <GitCompare className="w-3.5 h-3.5" />
              {showDiff ? "Hide Revision Diff" : "View Revision Diff"}
            </button>
          </div>
        </div>

        {/* Governance Requirement Alert */}
        {requiresLegalReviewer && (
          <div
            role="alert"
            className="rounded-lg border border-pastel-amber-border bg-pastel-amber-bg p-3 text-xs text-pastel-amber-text flex items-start gap-2.5"
          >
            <AlertTriangle className="w-4 h-4 mt-0.5 text-pastel-amber-text flex-shrink-0" />
            <div>
              <span className="font-semibold text-pastel-text">
                Mandatory Legal Reviewer Sign-Off Enforced (PRD §4.2 Y-11):
              </span>
              <p className="text-pastel-subtext mt-0.5">
                This revision contains {claimFindings.length} claim-type finding(s) (
                <span className="font-mono font-medium">Outdated / Unsupported</span>). Governance policy requires approval by <span className="font-bold text-pastel-indigo-text">legal_reviewer</span>.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Revision Diff View */}
      {showDiff && (
        <div className="rounded-xl border border-pastel-border bg-pastel-card p-4 shadow-pastel space-y-2">
          <div className="flex items-center justify-between border-b border-pastel-border pb-2">
            <span className="text-xs font-bold text-pastel-text flex items-center gap-1.5">
              <GitCompare className="w-3.5 h-3.5 text-pastel-indigo-text" />
              Tracked Change Diff: Revision v1 &rarr; v2
            </span>
            <span className="text-[11px] text-pastel-muted font-mono">
              Hash: {selectedRevision?.content_hash.substring(0, 12)}...
            </span>
          </div>

          <div className="p-3 bg-pastel-bg rounded-lg border border-pastel-border text-xs font-mono leading-relaxed flex flex-wrap gap-1">
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
        </div>
      )}

      {/* Items Pending Approval Queue */}
      <div className="rounded-xl border border-pastel-border bg-pastel-card p-4 shadow-pastel space-y-3">
        <h3 className="text-xs font-bold text-pastel-text">Pending Approvals</h3>

        <div className="divide-y divide-pastel-border/60">
          {revisions.map((rev) => (
            <div key={rev.id} className="py-3 flex items-center justify-between gap-3 flex-wrap">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-xs text-pastel-text">{rev.file_name}</span>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-pastel-bg border border-pastel-border">
                    v{rev.version}
                  </span>
                  <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full bg-pastel-amber-badge text-pastel-amber-text border border-pastel-amber-border">
                    {rev.approval_status}
                  </span>
                </div>
                <p className="text-[11px] text-pastel-muted font-mono">
                  SHA-256: {rev.content_hash.substring(0, 24)}...
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsRequesting(!isRequesting)}
                  className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-pastel-rose-text bg-white hover:bg-pastel-rose-bg border border-pastel-rose-border transition-all"
                >
                  Request Changes
                </button>

                <button
                  type="button"
                  disabled={!canApprove}
                  onClick={handleApprove}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 shadow-pastel transition-all ${
                    canApprove
                      ? "bg-pastel-green-badge hover:bg-pastel-green-border text-pastel-green-text border border-pastel-green-border cursor-pointer"
                      : "bg-pastel-border text-pastel-muted border-pastel-border cursor-not-allowed opacity-60"
                  }`}
                  title={
                    !canApprove
                      ? "Approval blocked: requires legal_reviewer due to claim-type findings."
                      : "Approve and bind SHA-256 hash"
                  }
                >
                  <FileCheck2 className="w-3.5 h-3.5" />
                  Approve (Hash-Bound)
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Request Changes Drawer */}
        {isRequesting && (
          <form onSubmit={handleRequestSubmit} className="pt-3 border-t border-pastel-border space-y-2">
            <label htmlFor="request-notes" className="block text-xs font-semibold text-pastel-text">
              Feedback Notes for Creator:
            </label>
            <textarea
              id="request-notes"
              rows={2}
              value={requestNotes}
              onChange={(e) => setRequestNotes(e.target.value)}
              placeholder="Specify required corrections before approval can proceed."
              required
              className="w-full text-xs p-2 rounded-lg border border-pastel-border bg-pastel-bg text-pastel-text"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsRequesting(false)}
                className="px-2.5 py-1 text-xs text-pastel-subtext hover:bg-pastel-hover rounded"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-3 py-1 text-xs font-semibold bg-pastel-rose-badge text-pastel-rose-text rounded border border-pastel-rose-border flex items-center gap-1"
              >
                <Send className="w-3 h-3" />
                Send Request
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Override Modal / Inline Form for Reviewer Override */}
      {overrideModal && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md rounded-xl border border-pastel-amber-border bg-white p-5 shadow-pastel-lg space-y-3">
            <h3 className="text-sm font-bold text-pastel-text flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4 text-pastel-amber-text" />
              Override Finding: Mandatory Written Reason
            </h3>
            <p className="text-xs text-pastel-subtext">
              Per PRD §4.2 Y-09 & Y-11, overriding a rule or claim finding requires an explicit, audited written justification.
            </p>

            <form onSubmit={handleOverrideSubmit} className="space-y-3">
              <textarea
                rows={3}
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Enter formal justification for overriding this finding..."
                required
                className="w-full text-xs p-2.5 rounded-lg border border-pastel-border bg-pastel-bg text-pastel-text focus:ring-2 focus:ring-pastel-indigo-border"
              />
              {overrideError && <p className="text-xs text-pastel-rose-text">{overrideError}</p>}

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setOverrideModal(null)}
                  className="px-3 py-1.5 text-xs text-pastel-subtext hover:bg-pastel-hover rounded-lg"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-3.5 py-1.5 text-xs font-semibold bg-pastel-amber-badge text-pastel-amber-text border border-pastel-amber-border rounded-lg shadow-pastel"
                >
                  Submit Audited Override
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

