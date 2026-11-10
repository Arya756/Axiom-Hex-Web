import React, { useState } from "react";
import { Source, SourceVersion } from "../../types";
import { BookOpen, GitCommit, Calendar, Tag, ChevronDown, ChevronRight, CheckCircle2, History } from "lucide-react";

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
      <div className="flex flex-wrap gap-2 pb-2 border-b border-pastel-border" role="tablist" aria-label="Source kind filters">
        {["all", "rule", "fact", "term", "asset"].map((kind) => (
          <button
            key={kind}
            role="tab"
            aria-selected={filter === kind}
            onClick={() => setFilter(kind)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium capitalize transition-all ${
              filter === kind
                ? "bg-pastel-blue-badge text-pastel-blue-text border border-pastel-blue-border font-semibold shadow-pastel"
                : "bg-pastel-card text-pastel-subtext hover:bg-pastel-hover border border-pastel-border"
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
              className="rounded-xl border border-pastel-border bg-pastel-card shadow-pastel transition-all overflow-hidden"
            >
              {/* Card Header */}
              <button
                onClick={() => toggleExpand(source.id)}
                aria-expanded={isExpanded}
                className="w-full text-left p-4 flex items-start justify-between gap-4 hover:bg-pastel-hover/60 transition-colors"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded-md bg-pastel-indigo-badge text-pastel-indigo-text border border-pastel-indigo-border">
                      {source.id}
                    </span>
                    <h3 className="text-sm font-semibold text-pastel-text">{source.name}</h3>
                    <span className="text-xs uppercase font-medium px-2 py-0.5 rounded-full bg-pastel-amber-badge text-pastel-amber-text border border-pastel-amber-border">
                      {source.kind}
                    </span>
                    <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-pastel-green-badge text-pastel-green-text border border-pastel-green-border flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      v{source.current_version} (Current)
                    </span>
                  </div>
                  {currentVersion && (
                    <p className="text-xs text-pastel-subtext line-clamp-2 pt-1 font-normal">
                      {currentVersion.body}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-2 text-pastel-muted flex-shrink-0 pt-1">
                  <span className="text-xs text-pastel-muted flex items-center gap-1">
                    <History className="w-3.5 h-3.5" />
                    {source.versions.length} ver
                  </span>
                  {isExpanded ? (
                    <ChevronDown className="w-4 h-4 text-pastel-subtext" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-pastel-subtext" />
                  )}
                </div>
              </button>

              {/* Version History Drawer */}
              {isExpanded && (
                <div className="p-4 pt-1 bg-pastel-bg/50 border-t border-pastel-border space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-pastel-subtext flex items-center gap-1.5">
                      <GitCommit className="w-3.5 h-3.5 text-pastel-indigo-text" />
                      Version History & Supersession Chain
                    </span>
                    <span className="text-[11px] text-pastel-muted">
                      Created: {new Date(source.created_at).toLocaleDateString()}
                    </span>
                  </div>

                  <div className="space-y-2">
                    {source.versions.map((ver) => {
                      const isCurrent = ver.version === source.current_version;
                      const isSuperseded = Boolean(ver.superseded_by);

                      return (
                        <div
                          key={ver.version}
                          className={`p-3 rounded-lg border text-xs transition-all ${
                            isCurrent
                              ? "bg-pastel-green-bg border-pastel-green-border text-pastel-text"
                              : "bg-pastel-card border-pastel-border text-pastel-muted"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2 mb-1.5">
                            <div className="flex items-center gap-2">
                              <span
                                className={`font-mono font-bold px-1.5 py-0.5 rounded text-[11px] ${
                                  isCurrent
                                    ? "bg-pastel-green-badge text-pastel-green-text"
                                    : "bg-pastel-hover text-pastel-subtext"
                                }`}
                              >
                                v{ver.version}
                              </span>
                              {isCurrent && (
                                <span className="font-semibold text-pastel-green-text text-[11px]">
                                  Active Standard
                                </span>
                              )}
                              {isSuperseded && (
                                <span className="font-medium text-pastel-rose-text bg-pastel-rose-badge px-1.5 py-0.5 rounded text-[10px]">
                                  Superseded by v{ver.superseded_by}
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] text-pastel-muted font-mono">
                              Hash: {ver.content_hash.substring(0, 10)}...
                            </span>
                          </div>

                          <p className={`text-xs ${isCurrent ? "text-pastel-text" : "text-pastel-subtext"}`}>
                            {ver.body}
                          </p>

                          {ver.value && (
                            <div className="mt-2 flex items-center gap-2 text-[11px]">
                              <span className="text-pastel-muted">Canonical value:</span>
                              <span className="font-semibold font-mono text-pastel-text bg-white px-1.5 py-0.5 rounded border border-pastel-border">
                                {ver.value} {ver.unit ?? ""}
                              </span>
                            </div>
                          )}

                          <div className="mt-2 pt-1 border-t border-pastel-border/60 flex items-center justify-between text-[10px] text-pastel-muted">
                            <span>Valid from: {new Date(ver.valid_from).toLocaleDateString()}</span>
                            {ver.valid_until && (
                              <span>Expired: {new Date(ver.valid_until).toLocaleDateString()}</span>
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

