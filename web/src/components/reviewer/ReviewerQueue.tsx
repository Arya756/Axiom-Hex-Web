import React, { useState } from "react";
import { Revision, Finding, UserRole } from "../../types";
import { diffWords } from "diff";
import {
  CheckCircle2,
  AlertTriangle,
  Scale,
  GitCompare,
  FileCheck2,
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
    <div className="space-y-5">
      {/* Revision Selection Header */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-sm space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-50 text-indigo-600">
              <Scale className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900">Governance & Review Queue</h2>
              <p className="text-xs text-slate-500">
                Role active: <span className="font-semibold capitalize text-indigo-600">{currentUserRole}</span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setShowDiff(!showDiff)}
              className={`px-3.5 py-2 rounded-xl text-xs font-semibold border flex items-center gap-1.5 transition-all duration-150 ${
                showDiff
                  ? "bg-indigo-50 text-indigo-700 border-indigo-200 shadow-sm"
                  : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50 shadow-sm"
              }`}
            >
              <GitCompare className="w-4 h-4 text-indigo-500" />
              {showDiff ? "Hide Revision Diff" : "View Revision Diff"}
            </button>
          </div>
        </div>

        {/* Governance Requirement Alert */}
        {requiresLegalReviewer && (
          <div
            role="alert"
            className="rounded-xl border border-amber-300 bg-amber-50/80 p-4 text-xs text-amber-900 flex items-start gap-3 shadow-sm"
          >
            <div className="p-1 rounded-lg bg-amber-100 text-amber-700 flex-shrink-0 mt-0.5">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <div className="space-y-1">
              <span className="font-bold text-slate-900">
                Mandatory Legal Reviewer Sign-Off Enforced (PRD §4.2 Y-11):
              </span>
              <p className="text-slate-700 leading-relaxed">
                This revision contains {claimFindings.length} claim-type finding(s) (
                <span className="font-mono font-semibold bg-white/80 px-1.5 py-0.5 rounded border border-amber-200">
                  Outdated / Unsupported
                </span>). Governance policy requires approval by <span className="font-bold text-indigo-700">legal_reviewer</span>.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Revision Diff View */}
      {showDiff && (
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <span className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <GitCompare className="w-4 h-4 text-indigo-600" />
              Tracked Change Diff: Revision v1 → v2
            </span>
            <span className="text-xs text-slate-500 font-mono bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">
              Hash: {selectedRevision?.content_hash.substring(0, 12)}...
            </span>
          </div>

          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 text-xs font-mono leading-relaxed flex flex-wrap gap-1.5 shadow-inner">
            {diffParts.map((part, index) => {
              if (part.added) {
                return (
                  <span
                    key={index}
                    className="bg-emerald-100 text-emerald-800 border border-emerald-300 px-1.5 py-0.5 rounded font-bold"
                  >
                    +{part.value}
                  </span>
                );
              }
              if (part.removed) {
                return (
                  <span
                    key={index}
                    className="bg-rose-100 text-rose-800 border border-rose-300 px-1.5 py-0.5 rounded line-through font-semibold"
                  >
                    -{part.value}
                  </span>
                );
              }
              return (
                <span key={index} className="text-slate-800">
                  {part.value}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Items Pending Approval Queue */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-slate-900 border-b border-slate-100 pb-3">Pending Approvals</h3>

        <div className="divide-y divide-slate-100">
          {revisions.map((rev) => (
            <div key={rev.id} className="py-4 flex items-center justify-between gap-4 flex-wrap">
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <span className="font-bold text-sm text-slate-900">{rev.file_name}</span>
                  <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                    v{rev.version}
                  </span>
                  <span className="text-xs uppercase font-bold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
                    {rev.approval_status}
                  </span>
                </div>
                <p className="text-xs text-slate-500 font-mono">
                  SHA-256: <span className="text-slate-700">{rev.content_hash.substring(0, 24)}...</span>
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => setIsRequesting(!isRequesting)}
                  className="px-3.5 py-2 rounded-xl text-xs font-semibold text-rose-700 bg-white hover:bg-rose-50 border border-rose-200 shadow-sm transition-all"
                >
                  Request Changes
                </button>

                <button
                  type="button"
                  disabled={!canApprove}
                  onClick={handleApprove}
                  className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center gap-2 shadow-sm transition-all duration-150 ${
                    canApprove
                      ? "bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 text-white shadow-emerald-200 cursor-pointer"
                      : "bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed opacity-60"
                  }`}
                  title={
                    !canApprove
                      ? "Approval blocked: requires legal_reviewer due to claim-type findings."
                      : "Approve and bind SHA-256 hash"
                  }
                >
                  <FileCheck2 className="w-4 h-4" />
                  Approve (Hash-Bound)
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Request Changes Drawer */}
        {isRequesting && (
          <form onSubmit={handleRequestSubmit} className="pt-4 border-t border-slate-200 space-y-3 bg-slate-50/60 p-4 rounded-xl">
            <label htmlFor="request-notes" className="block text-xs font-bold text-slate-800">
              Feedback Notes for Creator:
            </label>
            <textarea
              id="request-notes"
              rows={2}
              value={requestNotes}
              onChange={(e) => setRequestNotes(e.target.value)}
              placeholder="Specify required corrections before approval can proceed."
              required
              className="w-full text-xs p-3 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsRequesting(false)}
                className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-200/60 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 text-xs font-semibold bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white rounded-lg shadow-sm shadow-rose-200 flex items-center gap-1.5 transition-colors"
              >
                <Send className="w-3.5 h-3.5" />
                Send Request
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Override Modal / Inline Form for Reviewer Override */}
      {overrideModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-xl space-y-4">
            <div className="flex items-center gap-2.5 text-amber-700">
              <div className="p-2 rounded-xl bg-amber-50">
                <AlertTriangle className="w-5 h-5 text-amber-600" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">
                Override Finding: Mandatory Written Reason
              </h3>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              Per PRD §4.2 Y-09 & Y-11, overriding a rule or claim finding requires an explicit, audited written justification.
            </p>

            <form onSubmit={handleOverrideSubmit} className="space-y-3.5">
              <textarea
                rows={3}
                value={overrideReason}
                onChange={(e) => setOverrideReason(e.target.value)}
                placeholder="Enter formal justification for overriding this finding..."
                required
                className="w-full text-xs p-3 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
              />
              {overrideError && <p className="text-xs font-semibold text-rose-700">{overrideError}</p>}

              <div className="flex justify-end gap-2.5">
                <button
                  type="button"
                  onClick={() => setOverrideModal(null)}
                  className="px-3.5 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 text-xs font-semibold bg-amber-600 hover:bg-amber-700 active:bg-amber-800 text-white rounded-xl shadow-sm shadow-amber-200 transition-colors"
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
