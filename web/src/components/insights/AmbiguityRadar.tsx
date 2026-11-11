import React, { useState } from "react";
import { RadarData } from "../../types";
import {
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  ShieldCheck,
  Sparkles,
  GitCompare,
  ArrowUpRight,
} from "lucide-react";

interface AmbiguityRadarProps {
  data: RadarData;
  onInspectImpact?: (ruleId: string) => void;
}

export function AmbiguityRadar({ data, onInspectImpact }: AmbiguityRadarProps) {
  const [filter, setFilter] = useState<"all" | "flagged" | "controls">("all");

  const filteredRules = data.rules.filter((rule) => {
    if (filter === "flagged") return rule.flagged;
    if (filter === "controls") return rule.is_control;
    return true;
  });

  const falseFlagPct = (data.summary.false_flag_rate * 100).toFixed(1);

  return (
    <div className="space-y-5" role="region" aria-label="Guideline Ambiguity Radar">
      {/* Synthetic Data Disclosure Banner (Y-24) */}
      {data.summary.contains_synthetic && (
        <div
          role="note"
          className="rounded-2xl border border-purple-200 bg-purple-50/90 p-4 shadow-sm flex items-start justify-between gap-4 flex-wrap"
        >
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-xl bg-purple-100 text-purple-700 border border-purple-200 flex-shrink-0">
              <FlaskConical className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-sm font-bold text-purple-950">
                  Synthetic Calibration History Active
                </h2>
                <span className="text-[11px] font-bold uppercase tracking-wide px-2.5 py-0.5 rounded-full bg-purple-100 text-purple-800 border border-purple-200">
                  Synthetic Data Included ({data.summary.total_synthetic_findings} synthetic /{" "}
                  {data.summary.total_live_findings} live)
                </span>
              </div>
              <p className="text-xs text-purple-800/90 mt-1 leading-relaxed">
                Generated via real FastAPI decision and routing endpoints (`POST /revisions/&#123;id&#125;/review`
                and `POST /findings/&#123;id&#125;/decision`). Rules and findings tagged{" "}
                <span className="font-semibold">Synthetic</span> are explicitly distinguished from live user analytics.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Soft Pastel KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-2xl border border-rose-200 bg-rose-50/80 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-rose-800">Flagged Ambiguous Rules</span>
            <AlertTriangle className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-rose-950">{data.summary.flagged_count}</span>
            <span className="text-xs text-rose-700 font-medium">
              of {data.summary.total_rules_evaluated} rules evaluated
            </span>
          </div>
          <p className="text-[11px] text-rose-700 mt-1">
            Seeded ambiguous caught: {data.summary.seeded_ambiguous_flagged_count}/
            {data.summary.seeded_ambiguous_total}
          </p>
        </div>

        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/80 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-emerald-800">Control False-Flag Rate</span>
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-emerald-950">{falseFlagPct}%</span>
            <span className="text-xs text-emerald-700 font-medium">
              ({data.summary.false_flags}/{data.summary.control_rules_evaluated} clear controls)
            </span>
          </div>
          <p className="text-[11px] text-emerald-700 mt-1">
            Clear guidelines R-01 to R-04 remain unflagged
          </p>
        </div>

        <div className="rounded-2xl border border-sky-200 bg-sky-50/80 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-sky-800">Signal Thresholds (I3.2)</span>
            <Sparkles className="w-4 h-4 text-sky-600" />
          </div>
          <div className="mt-2 text-xs text-sky-900 space-y-0.5 font-medium">
            <p>
              Min sample: <span className="font-bold">n &ge; {data.thresholds.min_sample_size}</span> · Override:{" "}
              <span className="font-bold">&ge; {Math.round(data.thresholds.override_dispute_rate * 100)}%</span>
            </p>
            <p>
              Abstain: <span className="font-bold">&ge; {Math.round(data.thresholds.abstain_rate * 100)}%</span> ·
              Disagreement:{" "}
              <span className="font-bold">&ge; {Math.round(data.thresholds.disagreement_rate * 100)}%</span>
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-indigo-200 bg-indigo-50/80 p-4 shadow-sm">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-indigo-800">Sample Provenance</span>
            <GitCompare className="w-4 h-4 text-indigo-600" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-lg font-bold capitalize text-indigo-950">{data.summary.data_origin}</span>
            <span className="text-xs text-indigo-700">signal pool</span>
          </div>
          <p className="text-[11px] text-indigo-700 mt-1">
            {data.summary.total_synthetic_findings} synthetic · {data.summary.total_live_findings} live findings
          </p>
        </div>
      </div>

      {/* Filter Header */}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-sm font-bold text-slate-900">
            Live Signals from `rule_stats`, Decisions & Ingest Linter
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Every flagged rule displays exact signal counts and concrete finding examples (never just an opaque score).
          </p>
        </div>

        <div
          className="flex items-center gap-1.5 bg-slate-100/80 p-1 rounded-xl border border-slate-200"
          role="tablist"
          aria-label="Radar rule filter"
        >
          {(
            [
              { id: "all", label: `All (${data.rules.length})` },
              { id: "flagged", label: `Flagged (${data.summary.flagged_count})` },
              { id: "controls", label: `Clear Controls (${data.summary.control_rules_evaluated})` },
            ] as const
          ).map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={filter === tab.id}
              onClick={() => setFilter(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                filter === tab.id
                  ? "bg-white text-indigo-700 shadow-sm border border-slate-200/70"
                  : "text-slate-600 hover:text-slate-900"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Rule Cards */}
      <div className="space-y-4">
        {filteredRules.map((rule) => {
          const cardColors = rule.flagged
            ? "border-rose-200/90 bg-white ring-1 ring-rose-100"
            : "border-emerald-200/90 bg-white";

          return (
            <article
              key={rule.rule_id}
              className={`rounded-2xl border p-5 shadow-sm transition-all space-y-4 ${cardColors}`}
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-4 flex-wrap">
                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200">
                      {rule.rule_id}
                    </span>
                    <h3 className="text-sm font-bold text-slate-900">{rule.rule_name}</h3>
                    {rule.flagged ? (
                      <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-rose-50 text-rose-800 border border-rose-200 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        Flagged Ambiguous (Score {rule.ambiguity_score.toFixed(2)})
                      </span>
                    ) : (
                      <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        Clear Guideline {rule.is_control ? "(Control)" : ""}
                      </span>
                    )}
                    {rule.is_synthetic && (
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-purple-50 text-purple-800 border border-purple-200">
                        Synthetic
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">{rule.rule_body}</p>
                </div>

                {onInspectImpact && (
                  <button
                    type="button"
                    onClick={() => onInspectImpact(rule.rule_id)}
                    className="px-3 py-1.5 rounded-xl text-xs font-semibold bg-amber-50 hover:bg-amber-100 text-amber-900 border border-amber-200 flex items-center gap-1.5 flex-shrink-0"
                  >
                    Check Affected Drafts
                    <ArrowUpRight className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>

              {/* Explicit Flag Trigger Reasons */}
              {rule.flag_reasons.length > 0 && (
                <div className="flex flex-wrap gap-2">
                  {rule.flag_reasons.map((reason, idx) => (
                    <span
                      key={idx}
                      className="text-xs font-medium px-2.5 py-1 rounded-lg bg-amber-50 text-amber-900 border border-amber-200"
                    >
                      {reason}
                    </span>
                  ))}
                </div>
              )}

              {/* Evidence Counts Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2.5">
                <div className="rounded-xl bg-slate-50 border border-slate-200/80 p-2.5">
                  <span className="text-[11px] text-slate-500 block">Sample Size</span>
                  <span className="text-sm font-bold text-slate-900">
                    {rule.signals.total_findings} findings
                  </span>
                </div>
                <div className="rounded-xl bg-rose-50/70 border border-rose-200/80 p-2.5">
                  <span className="text-[11px] text-rose-700 block">Override / Dispute</span>
                  <span className="text-sm font-bold text-rose-950">
                    {rule.signals.overridden_count + rule.signals.disputed_count} (
                    {Math.round(rule.signals.override_dispute_rate * 100)}%)
                  </span>
                </div>
                <div className="rounded-xl bg-amber-50/70 border border-amber-200/80 p-2.5">
                  <span className="text-[11px] text-amber-800 block">Abstain / Low Conf</span>
                  <span className="text-sm font-bold text-amber-950">
                    {rule.signals.abstained_count} abst · {rule.signals.low_confidence_count} low
                  </span>
                </div>
                <div className="rounded-xl bg-purple-50/70 border border-purple-200/80 p-2.5">
                  <span className="text-[11px] text-purple-800 block">Disagreement</span>
                  <span className="text-sm font-bold text-purple-950">
                    {rule.signals.disagreement_count} conflicts (
                    {Math.round(rule.signals.disagreement_rate * 100)}%)
                  </span>
                </div>
                <div className="rounded-xl bg-sky-50/70 border border-sky-200/80 p-2.5">
                  <span className="text-[11px] text-sky-800 block">Collisions / Lint</span>
                  <span className="text-sm font-bold text-sky-950">
                    {rule.signals.collision_count > 0
                      ? `Collides: ${rule.signals.collisions.join(", ")}`
                      : rule.signals.missing_owner || rule.signals.missing_examples
                      ? "Missing metadata"
                      : "Clean"}
                  </span>
                </div>
              </div>

              {/* Concrete Example Findings (I3.2) */}
              {rule.example_findings.length > 0 && (
                <div className="rounded-xl bg-slate-50/80 border border-slate-200 p-3.5 space-y-2.5">
                  <h4 className="text-xs font-bold text-slate-700">
                    Evidence Examples ({rule.example_findings.length})
                  </h4>
                  <div className="space-y-2">
                    {rule.example_findings.map((ex) => (
                      <div
                        key={ex.finding_id}
                        className="rounded-xl bg-white border border-slate-200 p-3 text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-mono font-semibold text-indigo-700">
                              {ex.finding_id}
                            </span>
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 capitalize">
                              {ex.type}
                            </span>
                            <span className="text-slate-500">
                              Conf: {Math.round(ex.confidence * 100)}%
                            </span>
                            {ex.abstained && (
                              <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 font-semibold">
                                Abstained
                              </span>
                            )}
                            {ex.is_synthetic && (
                              <span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 font-semibold">
                                Synthetic
                              </span>
                            )}
                          </div>
                          <span className="font-semibold capitalize text-slate-700">
                            Status: {ex.status}
                          </span>
                        </div>
                        {ex.quote && (
                          <p className="text-slate-700 italic bg-amber-50/50 px-2.5 py-1 rounded border border-amber-100">
                            &ldquo;{ex.quote}&rdquo;
                          </p>
                        )}
                        <p className="text-slate-600">{ex.explanation}</p>
                        {ex.decisions.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {ex.decisions.map((d, di) => (
                              <span
                                key={di}
                                className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-indigo-50 text-indigo-800 border border-indigo-200"
                              >
                                <span className="font-bold uppercase">{d.action}</span>
                                {d.reason ? `— ${d.reason}` : ""}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}

