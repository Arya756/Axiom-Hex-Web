import React from "react";
import { ImpactAnalysisData } from "../../types";
import { AlertCircle, CheckCircle2, FileWarning, RefreshCw, Sparkles } from "lucide-react";

interface AffectedContentPanelProps {
  impact: ImpactAnalysisData | null;
  onRecheckItem?: (revisionId: string, title: string) => void;
  onClose?: () => void;
}

export function AffectedContentPanel({
  impact,
  onRecheckItem,
  onClose,
}: AffectedContentPanelProps) {
  if (!impact) return null;

  return (
    <section
      aria-label="Rule-change impact analysis panel"
      className="rounded-2xl border border-amber-200 bg-amber-50/70 p-5 shadow-sm space-y-4"
    >
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-amber-100 text-amber-800 border border-amber-200 flex-shrink-0">
            <FileWarning className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-bold text-slate-900">
                Impact Analysis for{" "}
                <span className="font-mono text-indigo-700">{impact.source_id}</span>
                {impact.source_name ? ` (${impact.source_name})` : ""}
              </h3>
              {impact.current_version && (
                <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-white text-slate-700 border border-amber-200">
                  Updated to v{impact.current_version}
                </span>
              )}
              <span className="text-xs font-bold px-2.5 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-200">
                {impact.affected_count} Draft / In-Review Items Affected
              </span>
            </div>
            <p className="text-xs text-slate-600 mt-1">
              Draft and in-review documents whose latest review run referenced{" "}
              <span className="font-semibold">{impact.source_id}</span> — including{" "}
              <span className="font-semibold text-sky-800">Supported claims</span> that previously passed.
            </p>
          </div>
        </div>

        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="text-xs font-semibold px-3 py-1.5 rounded-xl bg-white text-slate-600 hover:text-slate-900 border border-slate-200"
          >
            Dismiss
          </button>
        )}
      </div>

      {impact.affected_items.length === 0 ? (
        <div className="rounded-xl bg-white border border-emerald-200 p-4 text-xs text-emerald-800 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>No active draft or in-review documents reference {impact.source_id}.</span>
        </div>
      ) : (
        <div className="space-y-2.5">
          {impact.affected_items.map((item) => (
            <div
              key={`${item.content_id}_${item.revision_id}`}
              className="rounded-xl bg-white border border-slate-200 p-3.5 shadow-sm flex items-center justify-between gap-4 flex-wrap"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-bold text-slate-900">{item.title}</span>
                  <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-slate-100 text-slate-700">
                    v{item.version_num} ({item.revision_id})
                  </span>
                  <span className="text-[11px] font-semibold capitalize px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                    {item.revision_status}
                  </span>
                  {item.matched_via === "supported_claim" ? (
                    <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-sky-50 text-sky-800 border border-sky-200 flex items-center gap-1">
                      <Sparkles className="w-3 h-3" />
                      Supported Claim (Currently Passing)
                    </span>
                  ) : (
                    <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-800 border border-rose-200 flex items-center gap-1">
                      <AlertCircle className="w-3 h-3" />
                      Finding Cited ({item.findings_for_source_count})
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-slate-500">
                  Run: <span className="font-mono">{item.latest_run_id}</span> · Sensitivity:{" "}
                  <span className="uppercase font-semibold">{item.sensitivity}</span>
                </p>
              </div>

              {onRecheckItem && (
                <button
                  type="button"
                  onClick={() => onRecheckItem(item.revision_id, item.title)}
                  className="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold flex items-center gap-1.5 shadow-sm flex-shrink-0"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Queue Re-check
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

