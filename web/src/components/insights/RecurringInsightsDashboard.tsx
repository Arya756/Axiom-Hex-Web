import React from "react";
import { RecurringInsightsData } from "../../types";
import { BarChart3, CheckCircle2, FileText, FlaskConical, ShieldAlert } from "lucide-react";

interface RecurringInsightsDashboardProps {
  data: RecurringInsightsData;
}

export function RecurringInsightsDashboard({ data }: RecurringInsightsDashboardProps) {
  const maxRuleCount = Math.max(
    1,
    ...data.top_violated_rules.map((r) => r.total_count)
  );
  const maxTypeCount = Math.max(1, ...data.by_type.map((t) => t.count));

  const severityStyles: Record<string, string> = {
    critical: "bg-rose-50 border-rose-200 text-rose-900",
    high: "bg-amber-50 border-amber-200 text-amber-900",
    medium: "bg-sky-50 border-sky-200 text-sky-900",
    low: "bg-emerald-50 border-emerald-200 text-emerald-900",
  };

  return (
    <div className="space-y-5" role="region" aria-label="Recurring Insights Dashboard">
      {data.summary.contains_synthetic && (
        <div
          role="note"
          className="rounded-2xl border border-purple-200 bg-purple-50/90 p-4 shadow-sm flex items-center justify-between gap-4 flex-wrap"
        >
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-purple-100 text-purple-700 border border-purple-200">
              <FlaskConical className="w-4 h-4" />
            </div>
            <div className="text-xs text-purple-900">
              <span className="font-bold">Includes Synthetic History:</span>{" "}
              {data.summary.synthetic_findings} synthetic calibration findings alongside{" "}
              {data.summary.live_findings} live findings are labelled explicitly below.
            </div>
          </div>
          <span className="text-[11px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-purple-100 text-purple-800 border border-purple-200">
            Synthetic Labelled
          </span>
        </div>
      )}

      {/* KPI Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-indigo-200 bg-indigo-50/80 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-indigo-800">Total Violations Tracked</span>
            <BarChart3 className="w-4 h-4 text-indigo-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-indigo-950">{data.summary.total_findings}</p>
          <p className="text-[11px] text-indigo-700 mt-1">
            {data.summary.live_findings} live · {data.summary.synthetic_findings} synthetic
          </p>
        </div>

        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-800">Resolution Rate</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-emerald-950">
            {Math.round(data.summary.resolution_rate * 100)}%
          </p>
          <p className="text-[11px] text-emerald-700 mt-1">
            {data.summary.resolved_findings} resolved · {data.summary.open_findings} open
          </p>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-amber-50/80 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-amber-800">Overrides & Disputes</span>
            <ShieldAlert className="w-4 h-4 text-amber-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-amber-950">
            {data.summary.overridden_count + data.summary.disputed_count}
          </p>
          <p className="text-[11px] text-amber-800 mt-1">
            {data.summary.overridden_count} overridden · {data.summary.disputed_count} disputed
          </p>
        </div>

        <div className="rounded-2xl border border-sky-200 bg-sky-50/80 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-sky-800">Accepted Fixes</span>
            <FileText className="w-4 h-4 text-sky-600" />
          </div>
          <p className="mt-2 text-2xl font-bold text-sky-950">{data.summary.accepted_count}</p>
          <p className="text-[11px] text-sky-700 mt-1">Applied via evidence-first receipts</p>
        </div>
      </div>

      {/* Charts & Breakdown Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Top Violated Rules */}
        <div className="lg:col-span-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-4">
          <h3 className="text-sm font-bold text-slate-900">Top Recurring Rule Violations</h3>
          <div className="space-y-3">
            {data.top_violated_rules.map((rule) => {
              const widthPct = Math.max(8, Math.round((rule.total_count / maxRuleCount) * 100));
              return (
                <div key={rule.rule_id} className="space-y-1.5">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono font-bold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                        {rule.rule_id}
                      </span>
                      <span className="font-semibold text-slate-800">{rule.rule_name}</span>
                      {rule.is_synthetic && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-800 border border-purple-200">
                          Synthetic ({rule.synthetic_count})
                        </span>
                      )}
                    </div>
                    <span className="font-bold text-slate-700">
                      {rule.total_count} total ({rule.open_count} open)
                    </span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-indigo-400"
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Finding Type Distribution & Severity */}
        <div className="lg:col-span-5 space-y-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-3.5">
            <h3 className="text-sm font-bold text-slate-900">Violations by Finding Type</h3>
            <div className="space-y-2.5">
              {data.by_type.map((t) => {
                const widthPct = Math.max(8, Math.round((t.count / maxTypeCount) * 100));
                return (
                  <div key={t.type} className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="capitalize font-semibold text-slate-700">{t.type}</span>
                      <span className="text-slate-600 font-medium">
                        {t.count} ({Math.round(t.share * 100)}%)
                      </span>
                    </div>
                    <div className="w-full h-2 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-violet-400"
                        style={{ width: `${widthPct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
            <h3 className="text-sm font-bold text-slate-900">Severity Mix</h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              {data.by_severity.map((s) => (
                <div
                  key={s.severity}
                  className={`rounded-xl border p-3 text-center ${
                    severityStyles[s.severity] || "bg-slate-50 border-slate-200 text-slate-800"
                  }`}
                >
                  <span className="text-[11px] uppercase font-bold block">{s.severity}</span>
                  <span className="text-lg font-bold">{s.count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Hotspots Table */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm space-y-3">
        <h3 className="text-sm font-bold text-slate-900">Most Affected Documents</h3>
        <div className="divide-y divide-slate-100">
          {data.top_affected_content.map((doc) => (
            <div
              key={doc.content_id}
              className="py-2.5 flex items-center justify-between gap-4 text-xs"
            >
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-slate-900">{doc.title}</span>
                {doc.is_synthetic && (
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-800 border border-purple-200">
                    Synthetic
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <span className="font-semibold text-slate-700">{doc.total_findings} findings</span>
                <span className="px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-semibold">
                  {doc.open_findings} open
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

