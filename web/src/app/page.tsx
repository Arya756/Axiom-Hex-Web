"use client";

import React, { useState } from "react";
import { UserRole, Finding, Source, ContentUnit, IntentCard, Revision, SensitivityLevel, ReviewRunProgress, FindingDecision } from "../types";
import {
  SEEDED_SOURCES,
  SEEDED_FINDINGS,
  SEEDED_CONTENT_UNITS,
  INITIAL_INTENT_CARD,
  SEEDED_REVISION,
} from "../lib/mockData";
import { Navbar } from "../components/layout/Navbar";
import { AxeDisclosure } from "../components/common/AxeDisclosure";
import { SourceList } from "../components/admin/SourceList";
import { SourceForm } from "../components/admin/SourceForm";
import { UploadDrawer } from "../components/creator/UploadDrawer";
import { IntentCardDrawer } from "../components/creator/IntentCardDrawer";
import { FindingCard } from "../components/findings/FindingCard";
import { DocumentViewer } from "../components/viewer/DocumentViewer";
import { ReviewerQueue } from "../components/reviewer/ReviewerQueue";
import { Filter, CheckCircle2, AlertCircle, FileText, Sparkles } from "lucide-react";

export default function Home() {
  const [currentRole, setCurrentRole] = useState<UserRole>("creator");
  const [activeTab, setActiveTab] = useState<"workspace" | "admin" | "reviewer">("workspace");

  // State
  const [sources, setSources] = useState<Source[]>(SEEDED_SOURCES);
  const [units, setUnits] = useState<ContentUnit[]>(SEEDED_CONTENT_UNITS);
  const [findings, setFindings] = useState<Finding[]>(SEEDED_FINDINGS);
  const [intentCard, setIntentCard] = useState<IntentCard>(INITIAL_INTENT_CARD);
  const [revisions, setRevisions] = useState<Revision[]>([SEEDED_REVISION]);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>("f_81c2");
  const [runProgress, setRunProgress] = useState<ReviewRunProgress | null>(null);
  const [findingFilter, setFindingFilter] = useState<string>("all");
  const [statusBanner, setStatusBanner] = useState<{ message: string; type: "success" | "info" } | null>(null);

  // Finding filtering
  const filteredFindings = findings.filter((f) => {
    if (findingFilter === "all") return true;
    if (findingFilter === "open") return f.status === "open";
    if (findingFilter === "resolved") return f.status !== "open";
    return f.type === findingFilter;
  });

  // Action handlers
  const handleSelectFinding = (findingId: string) => {
    setSelectedFindingId(findingId);
  };

  const handleDecision = (findingId: string, decision: FindingDecision, reason?: string) => {
    setFindings((prev) =>
      prev.map((f) => {
        if (f.finding_id !== findingId) return f;
        const newStatus =
          decision === "accept"
            ? "accepted"
            : decision === "dispute"
            ? "disputed"
            : decision === "override"
            ? "overridden"
            : "rejected";

        return {
          ...f,
          status: newStatus,
          decision,
          decision_reason: reason,
        };
      })
    );

    // If accept, update the text unit inline!
    if (decision === "accept") {
      const finding = findings.find((f) => f.finding_id === findingId);
      if (finding && finding.suggested_fix) {
        const fixText = finding.suggested_fix.text;
        setUnits((prevUnits) =>
          prevUnits.map((u) => {
            if (u.unit_id === finding.span.unit_id) {
              const updatedText = u.text.replace(finding.span.quote, fixText);
              return { ...u, text: updatedText };
            }
            return u;
          })
        );
      }
    }

    setStatusBanner({
      message: `Finding ${findingId} marked as ${decision.toUpperCase()}${reason ? ` with justification: "${reason}"` : ""}.`,
      type: "success",
    });
    setTimeout(() => setStatusBanner(null), 4000);
  };

  const handleEditFix = (findingId: string, editedText: string) => {
    setFindings((prev) =>
      prev.map((f) => {
        if (f.finding_id !== findingId) return f;
        return {
          ...f,
          suggested_fix: {
            ...f.suggested_fix!,
            text: editedText,
            rechecked: true,
          },
        };
      })
    );
    setStatusBanner({
      message: `Fix edited for ${findingId}. Re-checked against intent card constraints.`,
      type: "info",
    });
  };

  const handleUploadSuccess = (file: File, sensitivity: SensitivityLevel) => {
    setRunProgress({
      status: "running",
      progress: 25,
      active_step: "Parsing content & extracting Intent Card (T9)",
      findings_count: 0,
    });

    setTimeout(() => {
      setRunProgress({
        status: "running",
        progress: 60,
        active_step: "Deterministic terminology & temporal fact ledger checks",
        findings_count: 2,
      });
    }, 700);

    setTimeout(() => {
      setRunProgress({
        status: "running",
        progress: 85,
        active_step: "Citation Verifier checking evidence against sources",
        findings_count: 3,
      });
    }, 1400);

    setTimeout(() => {
      setRunProgress({
        status: "done",
        progress: 100,
        active_step: "Review complete",
        findings_count: 4,
        cached: false,
      });

      const newRev: Revision = {
        id: `rev_${Date.now().toString(36)}`,
        content_id: "cnt_doc_01",
        version: revisions.length + 1,
        content_hash: "sha256_" + Math.random().toString(36).substring(2, 12),
        file_name: file.name,
        file_type: file.name.endsWith(".pdf") ? "pdf" : file.name.endsWith(".png") ? "image" : "markdown",
        sensitivity,
        approval_status: "in_review",
        created_at: new Date().toISOString(),
      };
      setRevisions((prev) => [newRev, ...prev]);

      setStatusBanner({
        message: `Uploaded "${file.name}" as revision v${newRev.version}. Pre-check completed.`,
        type: "success",
      });
    }, 2000);
  };

  const handleApproveRevision = (revisionId: string, contentHash: string) => {
    setRevisions((prev) =>
      prev.map((r) =>
        r.id === revisionId
          ? { ...r, approval_status: "approved" }
          : r
      )
    );
    setStatusBanner({
      message: `Revision ${revisionId} Approved! Locked to content hash ${contentHash.substring(0, 16)}...`,
      type: "success",
    });
  };

  const handleRequestChanges = (revisionId: string, notes: string) => {
    setRevisions((prev) =>
      prev.map((r) =>
        r.id === revisionId
          ? { ...r, approval_status: "in_review" }
          : r
      )
    );
    setStatusBanner({
      message: `Changes requested on revision ${revisionId}. Creator notified: "${notes}"`,
      type: "info",
    });
  };

  const handleOverrideFinding = (findingId: string, reason: string) => {
    handleDecision(findingId, "override", reason);
  };

  return (
    <div className="min-h-screen bg-pastel-bg text-pastel-text flex flex-col">
      {/* Navbar with role switcher & tabs */}
      <Navbar
        currentRole={currentRole}
        onRoleChange={setCurrentRole}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      {/* Main Workspace Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8 space-y-5">
        {/* WCAG 2.2 AA Partial Coverage Disclosure Banner */}
        <AxeDisclosure />

        {/* Global Status Banner */}
        {statusBanner && (
          <div
            role="status"
            className={`p-3 rounded-xl border text-xs flex items-center gap-2 shadow-pastel ${
              statusBanner.type === "success"
                ? "bg-pastel-green-bg border-pastel-green-border text-pastel-green-text"
                : "bg-pastel-indigo-bg border-pastel-indigo-border text-pastel-indigo-text"
            }`}
          >
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span className="font-medium">{statusBanner.message}</span>
          </div>
        )}

        {/* TAB 1: WORKSPACE (Creator upload, Intent Card, Viewer, Finding Cards) */}
        {activeTab === "workspace" && (
          <div className="space-y-5">
            {/* Top Row: Upload & Intent Card Drawer */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              <div className="lg:col-span-6">
                <UploadDrawer
                  onUploadSuccess={handleUploadSuccess}
                  runProgress={runProgress}
                />
              </div>
              <div className="lg:col-span-6">
                <IntentCardDrawer
                  intentCard={intentCard}
                  onSaveIntentCard={setIntentCard}
                  onRerunConstrainedFixes={() => {
                    setStatusBanner({
                      message: "Re-running LLM minimal-edit fixes constrained by updated Intent Card...",
                      type: "info",
                    });
                  }}
                />
              </div>
            </div>

            {/* Split Screen: Document Viewer (Left) + Finding Cards (Right) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
              {/* Left Column: Interactive Document Canvas with Highlights & Bounding Boxes */}
              <div className="lg:col-span-7 h-[780px] sticky top-20">
                <DocumentViewer
                  units={units}
                  findings={findings}
                  selectedFindingId={selectedFindingId}
                  onSelectFinding={handleSelectFinding}
                  fileType="markdown"
                />
              </div>

              {/* Right Column: Evidence-First Finding Cards */}
              <div className="lg:col-span-5 space-y-4">
                <div className="rounded-xl border border-pastel-border bg-pastel-card p-4 shadow-pastel space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-xs font-bold text-pastel-text flex items-center gap-1.5">
                        <Sparkles className="w-4 h-4 text-pastel-indigo-text" />
                        Automated Receipts & Findings ({findings.length})
                      </h2>
                      <p className="text-[11px] text-pastel-muted">
                        Evidence-first layout: citations validated by Verifier
                      </p>
                    </div>
                  </div>

                  {/* Filter Pills */}
                  <div className="flex items-center gap-1.5 flex-wrap pt-1 border-t border-pastel-border" role="tablist" aria-label="Finding filters">
                    {["all", "open", "resolved", "outdated", "violation", "unsupported", "accessibility"].map((f) => (
                      <button
                        key={f}
                        role="tab"
                        aria-selected={findingFilter === f}
                        onClick={() => setFindingFilter(f)}
                        className={`px-2 py-1 rounded text-[11px] font-medium capitalize transition-all ${
                          findingFilter === f
                            ? "bg-pastel-indigo-badge text-pastel-indigo-text font-semibold border border-pastel-indigo-border"
                            : "bg-pastel-bg text-pastel-subtext hover:bg-pastel-hover border border-pastel-border"
                        }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Cards List */}
                <div className="space-y-3" role="region" aria-label="Evidence-first finding cards list">
                  {filteredFindings.map((finding) => (
                    <FindingCard
                      key={finding.finding_id}
                      finding={finding}
                      isSelected={finding.finding_id === selectedFindingId}
                      onSelect={(f) => handleSelectFinding(f.finding_id)}
                      onDecision={handleDecision}
                      onEditFix={handleEditFix}
                    />
                  ))}
                  {filteredFindings.length === 0 && (
                    <div className="p-8 text-center bg-pastel-card rounded-xl border border-pastel-border text-xs text-pastel-muted">
                      No findings match the selected filter.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: REVIEWER QUEUE & GOVERNANCE */}
        {activeTab === "reviewer" && (
          <div className="max-w-4xl mx-auto">
            <ReviewerQueue
              revisions={revisions}
              findings={findings}
              currentUserRole={currentRole}
              onApproveRevision={handleApproveRevision}
              onRequestChanges={handleRequestChanges}
              onOverrideFinding={handleOverrideFinding}
            />
          </div>
        )}

        {/* TAB 3: ADMIN SOURCES & BRAND KIT COMPILER */}
        {activeTab === "admin" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            <div className="lg:col-span-5 space-y-4">
              <SourceForm
                onAddSource={(newSource) => setSources((prev) => [newSource, ...prev])}
                onImportKit={(count) => {
                  setStatusBanner({
                    message: `Imported and compiled ${count} sources into Brand Kit.`,
                    type: "success",
                  });
                }}
              />
            </div>

            <div className="lg:col-span-7 space-y-4">
              <SourceList sources={sources} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

