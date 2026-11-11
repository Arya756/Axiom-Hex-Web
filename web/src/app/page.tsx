"use client";

import React, { useState } from "react";
import {
  UserRole,
  Finding,
  Source,
  ContentUnit,
  IntentCard,
  Revision,
  SensitivityLevel,
  ReviewRunProgress,
  FindingDecision,
  RadarData,
  ImpactAnalysisData,
  RecurringInsightsData,
} from "../types";
import {
  SEEDED_SOURCES,
  SEEDED_FINDINGS,
  SEEDED_CONTENT_UNITS,
  INITIAL_INTENT_CARD,
  SEEDED_REVISION,
  SEEDED_RADAR_DATA,
  SEEDED_IMPACT_MAP,
  SEEDED_RECURRING_INSIGHTS,
} from "../lib/mockData";
import { Navbar, AppTab } from "../components/layout/Navbar";
import { AxeDisclosure } from "../components/common/AxeDisclosure";
import { SourceList } from "../components/admin/SourceList";
import { SourceForm } from "../components/admin/SourceForm";
import { AffectedContentPanel } from "../components/admin/AffectedContentPanel";
import { UploadDrawer } from "../components/creator/UploadDrawer";
import { IntentCardDrawer } from "../components/creator/IntentCardDrawer";
import { FindingCard } from "../components/findings/FindingCard";
import { DocumentViewer } from "../components/viewer/DocumentViewer";
import { ReviewerQueue } from "../components/reviewer/ReviewerQueue";
import { AmbiguityRadar } from "../components/insights/AmbiguityRadar";
import { RecurringInsightsDashboard } from "../components/insights/RecurringInsightsDashboard";
import { CheckCircle2, Sparkles, Info, UploadCloud, Compass, ChevronDown, ChevronUp, FileText } from "lucide-react";

export default function Home() {
  const [currentRole, setCurrentRole] = useState<UserRole>("creator");
  const [activeTab, setActiveTab] = useState<AppTab>("workspace");

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
  const [radarData] = useState<RadarData>(SEEDED_RADAR_DATA);
  const [recurringInsights] = useState<RecurringInsightsData>(SEEDED_RECURRING_INSIGHTS);
  const [activeImpact, setActiveImpact] = useState<ImpactAnalysisData | null>(null);

  // Workspace panel toggles (clean, space-efficient control)
  const [showUploadPanel, setShowUploadPanel] = useState<boolean>(false);
  const [showIntentPanel, setShowIntentPanel] = useState<boolean>(false);

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

    // If accept, update the text unit inline
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
    setShowUploadPanel(true);
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

  const handleInspectImpact = (sourceId: string) => {
    const matchedSource = sources.find((s) => s.id === sourceId);
    const presetImpact = SEEDED_IMPACT_MAP[sourceId];
    if (presetImpact) {
      setActiveImpact({
        ...presetImpact,
        source_name: matchedSource?.name ?? presetImpact.source_name,
        current_version: matchedSource?.current_version ?? presetImpact.current_version,
      });
    } else {
      setActiveImpact({
        source_id: sourceId,
        source_name: matchedSource?.name ?? sourceId,
        source_kind: matchedSource?.kind,
        current_version: matchedSource?.current_version ?? 1,
        affected_count: 0,
        affected_items: [],
      });
    }
    setActiveTab("admin");
  };

  const handleCreateNewSourceVersion = (
    sourceId: string,
    body: string,
    value?: string,
    unit?: string
  ) => {
    const nowIso = new Date().toISOString();
    let updatedVer = 1;
    setSources((prev) =>
      prev.map((src) => {
        if (src.id !== sourceId) return src;
        updatedVer = src.current_version + 1;
        const updatedVersions = src.versions.map((v) =>
          v.version === src.current_version
            ? { ...v, valid_until: nowIso, superseded_by: updatedVer }
            : v
        );
        return {
          ...src,
          current_version: updatedVer,
          versions: [
            ...updatedVersions,
            {
              version: updatedVer,
              content_hash: "sha256_" + Math.random().toString(36).substring(2, 10),
              body,
              value,
              unit,
              valid_from: nowIso,
              valid_until: null,
              superseded_by: null,
              created_at: nowIso,
            },
          ],
        };
      })
    );
    const matched = sources.find((s) => s.id === sourceId);
    const presetImpact = SEEDED_IMPACT_MAP[sourceId];
    setActiveImpact(
      presetImpact
        ? {
            ...presetImpact,
            source_name: matched?.name ?? presetImpact.source_name,
            current_version: (matched?.current_version ?? 1) + 1,
          }
        : {
            source_id: sourceId,
            source_name: matched?.name ?? sourceId,
            source_kind: matched?.kind,
            current_version: (matched?.current_version ?? 1) + 1,
            affected_count: 0,
            affected_items: [],
          }
    );
    setStatusBanner({
      message: `Published v${(matched?.current_version ?? 1) + 1} for ${sourceId}. Impact analysis loaded for affected draft/in-review items.`,
      type: "success",
    });
  };

  const currentRevision = revisions[0] || SEEDED_REVISION;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
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
            className={`p-4 rounded-2xl border text-xs sm:text-sm flex items-center gap-3 shadow-sm transition-all duration-200 ${
              statusBanner.type === "success"
                ? "bg-emerald-50 border-emerald-200 text-emerald-900"
                : "bg-indigo-50 border-indigo-200 text-indigo-900"
            }`}
          >
            {statusBanner.type === "success" ? (
              <div className="p-1 rounded-full bg-emerald-100 text-emerald-700 flex-shrink-0">
                <CheckCircle2 className="w-4 h-4" />
              </div>
            ) : (
              <div className="p-1 rounded-full bg-indigo-100 text-indigo-700 flex-shrink-0">
                <Info className="w-4 h-4" />
              </div>
            )}
            <span className="font-semibold">{statusBanner.message}</span>
          </div>
        )}

        {/* TAB 1: WORKSPACE */}
        {activeTab === "workspace" && (
          <div className="space-y-5">
            {/* Unified Workspace Control Ribbon: Eliminates top-row empty voids */}
            <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm flex items-center justify-between gap-4 flex-wrap">
              {/* Active Draft Metadata */}
              <div className="flex items-center gap-3 flex-wrap">
                <div className="w-10 h-10 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center flex-shrink-0">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold text-slate-900">{currentRevision.file_name}</span>
                    <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200">
                      v{currentRevision.version}
                    </span>
                    <span className="text-xs uppercase font-semibold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                      {currentRevision.sensitivity}
                    </span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
                      {findings.length} Findings
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5 font-normal">
                    Target: <span className="font-semibold text-slate-700">{intentCard.purpose}</span> · Audience: <span className="text-slate-700 font-medium">{intentCard.audience}</span>
                  </p>
                </div>
              </div>

              {/* Action Toggles: Expand drawer only when needed */}
              <div className="flex items-center gap-2.5">
                <button
                  type="button"
                  onClick={() => {
                    setShowUploadPanel((prev) => !prev);
                    if (!showUploadPanel) setShowIntentPanel(false);
                  }}
                  className={`px-3.5 py-2 rounded-xl text-xs font-semibold border flex items-center gap-1.5 transition-all duration-150 ${
                    showUploadPanel
                      ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                      : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50 shadow-sm"
                  }`}
                >
                  <UploadCloud className="w-4 h-4" />
                  {showUploadPanel ? "Close Upload" : "Upload Draft"}
                  {showUploadPanel ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setShowIntentPanel((prev) => !prev);
                    if (!showIntentPanel) setShowUploadPanel(false);
                  }}
                  className={`px-3.5 py-2 rounded-xl text-xs font-semibold border flex items-center gap-1.5 transition-all duration-150 ${
                    showIntentPanel
                      ? "bg-violet-600 text-white border-violet-600 shadow-sm"
                      : "bg-white text-slate-700 border-slate-300 hover:bg-slate-50 shadow-sm"
                  }`}
                >
                  <Compass className="w-4 h-4" />
                  {showIntentPanel ? "Close Intent Card" : "Intent Card Constraints"}
                  {showIntentPanel ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                </button>
              </div>
            </div>

            {/* Conditionally rendered panels (clean, full-width, zero empty void) */}
            {showUploadPanel && (
              <div className="transition-all duration-200">
                <UploadDrawer
                  onUploadSuccess={handleUploadSuccess}
                  runProgress={runProgress}
                />
              </div>
            )}

            {showIntentPanel && (
              <div className="transition-all duration-200">
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
            )}

            {/* Split Screen: Document Canvas (Left) + Finding Cards (Right) */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
              {/* Left Column: Interactive Document Canvas */}
              <div className="lg:col-span-7 h-[calc(100vh-14rem)] min-h-[640px] sticky top-20">
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
                <div className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-5 shadow-sm space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                        <Sparkles className="w-4 h-4 text-indigo-600" />
                        Automated Receipts & Findings ({findings.length})
                      </h2>
                      <p className="text-xs text-slate-500 mt-0.5">
                        Evidence-first layout: citations validated by Verifier
                      </p>
                    </div>
                  </div>

                  {/* Filter Pills */}
                  <div
                    className="flex items-center gap-1.5 flex-wrap pt-2 border-t border-slate-100"
                    role="tablist"
                    aria-label="Finding filters"
                  >
                    {["all", "open", "resolved", "outdated", "violation", "unsupported", "accessibility"].map((f) => (
                      <button
                        key={f}
                        role="tab"
                        aria-selected={findingFilter === f}
                        onClick={() => setFindingFilter(f)}
                        className={`px-3 py-1 rounded-full text-xs font-semibold capitalize transition-all duration-150 ${
                          findingFilter === f
                            ? "bg-indigo-600 text-white shadow-sm shadow-indigo-200"
                            : "bg-slate-100 text-slate-600 hover:bg-slate-200/80 hover:text-slate-900"
                        }`}
                      >
                        {f}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Cards List */}
                <div className="space-y-3.5" role="region" aria-label="Evidence-first finding cards list">
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
                    <div className="p-10 text-center bg-white rounded-2xl border border-slate-200 text-xs sm:text-sm text-slate-500 shadow-sm">
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
          <div className="space-y-5">
            {activeImpact && (
              <AffectedContentPanel
                impact={activeImpact}
                onClose={() => setActiveImpact(null)}
                onRecheckItem={(revId, title) => {
                  setStatusBanner({
                    message: `Queued background re-check run for "${title}" (${revId}).`,
                    type: "info",
                  });
                }}
              />
            )}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
              <div className="lg:col-span-5 space-y-4">
                <SourceForm
                  onAddSource={(newSource) => {
                    setSources((prev) => [newSource, ...prev]);
                    handleInspectImpact(newSource.id);
                  }}
                  onImportKit={(count) => {
                    setStatusBanner({
                      message: `Imported and compiled ${count} sources into Brand Kit.`,
                      type: "success",
                    });
                  }}
                />
              </div>

              <div className="lg:col-span-7 space-y-4">
                <SourceList
                  sources={sources}
                  onCreateNewVersion={handleCreateNewSourceVersion}
                  onCheckImpact={handleInspectImpact}
                />
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: GUIDELINE AMBIGUITY RADAR (Y-21, Y-24, I3) */}
        {activeTab === "radar" && (
          <AmbiguityRadar data={radarData} onInspectImpact={handleInspectImpact} />
        )}

        {/* TAB 5: RECURRING INSIGHTS DASHBOARD (Y-23) */}
        {activeTab === "insights" && (
          <RecurringInsightsDashboard data={recurringInsights} />
        )}
      </main>
    </div>
  );
}
