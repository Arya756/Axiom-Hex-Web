import React, { useState } from "react";
import { Source } from "../../types";
import { GitCommit, ChevronDown, ChevronRight, CheckCircle2, History } from "lucide-react";

interface SourceListProps {
  sources: Source[];
  onSelectSource?: (source: Source) => void;
}

export function SourceList({ sources, onSelectSource }: SourceListProps) {
  const [filter, setFilter] = useState<string>("all");
  const [expandedSourceId, setExpandedSourceId] = useState<string | null>("F-112");

  const filteredSources = sources.filter((s) => (filter === "all" ? true : s.kind === filter));

  const toggleExpand = (id: string) => {
    setExpandedSourceId((prev) => (prev === id ? null : id));
  };

  return (
    <div className="space-y-4">
      {/* Filter Tabs */}
      <div className="flex flex-wrap gap-2 pb-2 border-b border-slate-200" role="tablist" aria-label="Source kind filters">
        {["all", "rule", "fact", "term", "asset"].map((kind) => (
          <button
            key={kind}
            role="tab"
            aria-selected={filter === kind}
            onClick={() => setFilter(kind)}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold capitalize transition-all duration-150 ${
              filter === kind
                ? "bg-indigo-600 text-white shadow-sm shadow-indigo-200"
                : "bg-white text-slate-600 hover:bg-slate-100 hover:text-slate-900 border border-slate-200"
            }`}
          >
            {kind}
          </button>
        ))}
      </div>

      {/* Sources Accordion List */}
      <div className="space-y-3" role="region" aria-label="Sources repository list">
        {filteredSources.map((source) => {
          const isExpanded = expandedSourceId === source.id;
          const currentVersion = source.versions.find((v) => v.version === source.current_version);

          return (
            <div
              key={source.id}
              className="rounded-2xl border border-slate-200/90 bg-white shadow-sm hover:shadow-md transition-all duration-200 overflow-hidden"
            >
              {/* Card Header */}
              <button
                onClick={() => toggleExpand(source.id)}
                aria-expanded={isExpanded}
                className="w-full text-left p-5 flex items-start justify-between gap-4 hover:bg-slate-50/80 transition-colors"
              >
                <div className="space-y-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-md bg-indigo-50 text-indigo-700 border border-indigo-200/80">
                      {source.id}
                    </span>
                    <h3 className="text-sm font-bold text-slate-900">{source.name}</h3>
                    <span className="text-xs uppercase font-semibold px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200">
                      {source.kind}
                    </span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      v{source.current_version} (Current)
                    </span>
                  </div>
                  {/* Full body text with no line-clamp truncation cutoffs */}
                  {currentVersion && (
                    <p className="text-xs text-slate-600 pt-0.5 font-normal leading-relaxed">
                      {currentVersion.body}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 text-slate-400 flex-shrink-0 pt-0.5">
                  <span className="text-xs text-slate-500 font-medium flex items-center gap-1 bg-slate-100 px-2 py-0.5 rounded-full">
                    <History className="w-3.5 h-3.5" />
                    {source.versions.length} ver
                  </span>
                  <div className="p-1 rounded-lg bg-slate-100 text-slate-600">
                    {isExpanded ? (
                      <ChevronDown className="w-4 h-4" />
                    ) : (
                      <ChevronRight className="w-4 h-4" />
                    )}
                  </div>
                </div>
              </button>

              {/* Version History Drawer */}
              {isExpanded && (
                <div className="p-5 pt-2 bg-slate-50/70 border-t border-slate-100 space-y-3.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-700 flex items-center gap-1.5">
                      <GitCommit className="w-4 h-4 text-indigo-600" />
                      Version History & Supersession Chain
                    </span>
                    <span className="text-[11px] text-slate-500 font-medium">
                      Created: {new Date(source.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    {source.versions.map((ver) => {
                      const isCurrent = ver.version === source.current_version;
                      const isSuperseded = Boolean(ver.superseded_by);

                      return (
                        <div
                          key={ver.version}
                          className={`p-3.5 rounded-xl border text-xs transition-all ${
                            isCurrent
                              ? "bg-white border-emerald-300 ring-2 ring-emerald-500/10 shadow-sm"
                              : "bg-white border-slate-200 text-slate-500"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2 mb-2">
                            <div className="flex items-center gap-2">
                              <span
                                className={`font-mono font-bold px-2 py-0.5 rounded text-xs ${
                                  isCurrent
                                    ? "bg-emerald-100 text-emerald-800 border border-emerald-200"
                                    : "bg-slate-100 text-slate-700"
                                }`}
                              >
                                v{ver.version}
                              </span>
                              {isCurrent && (
                                <span className="font-bold text-emerald-700 text-xs">
                                  Active Standard
                                </span>
                              )}
                              {isSuperseded && (
                                <span className="font-semibold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded-full text-[10px]">
                                  Superseded by v{ver.superseded_by}
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-slate-500 font-mono">
                              Hash: {ver.content_hash.substring(0, 10)}...
                            </span>
                          </div>

                          <p className={`text-xs leading-relaxed ${isCurrent ? "text-slate-800 font-medium" : "text-slate-600"}`}>
                            {ver.body}
                          </p>

                          {ver.value && (
                            <div className="mt-2.5 flex items-center gap-2 text-xs">
                              <span className="text-slate-500">Canonical value:</span>
                              <span className="font-bold font-mono text-slate-900 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                                {ver.value} {ver.unit ?? ""}
                              </span>
                            </div>
                          )}

                          <div className="mt-2.5 pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
                            <span>Valid from: {new Date(ver.valid_from).toLocaleDateString()}</span>
                            {ver.valid_until && (
                              <span className="text-rose-600 font-medium">Expired: {new Date(ver.valid_until).toLocaleDateString()}</span>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
