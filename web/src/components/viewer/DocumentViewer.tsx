import React, { useState } from "react";
import { ContentUnit, Finding } from "../../types";
import { FileText, Image as ImageIcon, ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

interface DocumentViewerProps {
  units: ContentUnit[];
  findings: Finding[];
  selectedFindingId?: string | null;
  onSelectFinding?: (findingId: string) => void;
  fileType?: "markdown" | "text" | "pdf" | "docx" | "image";
  fileUrl?: string;
}

export function DocumentViewer({
  units,
  findings,
  selectedFindingId,
  onSelectFinding,
  fileType = "markdown",
  fileUrl,
}: DocumentViewerProps) {
  const [zoom, setZoom] = useState(100);

  // Map findings by unit_id for quick highlight resolution
  const findingByUnit = findings.reduce<Record<string, Finding[]>>((acc, f) => {
    const uid = f.span.unit_id;
    if (!acc[uid]) acc[uid] = [];
    acc[uid].push(f);
    return acc;
  }, {});

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 15, 175));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 15, 75));
  const handleResetZoom = () => setZoom(100);

  return (
    <div className="rounded-xl border border-pastel-border bg-pastel-card shadow-pastel overflow-hidden flex flex-col h-full">
      {/* Viewer Toolbar */}
      <div className="p-3 bg-pastel-bg/80 border-b border-pastel-border flex items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-pastel-indigo-text" />
          <span className="font-semibold text-pastel-text capitalize">{fileType} Review Canvas</span>
          <span className="text-[11px] text-pastel-muted">({units.length} content units parsed)</span>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1.5 bg-white border border-pastel-border rounded-lg p-0.5">
          <button
            type="button"
            onClick={handleZoomOut}
            aria-label="Zoom out"
            className="p-1 rounded hover:bg-pastel-hover text-pastel-subtext"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-[11px] font-mono px-1.5 text-pastel-text min-w-[3rem] text-center">
            {zoom}%
          </span>
          <button
            type="button"
            onClick={handleZoomIn}
            aria-label="Zoom in"
            className="p-1 rounded hover:bg-pastel-hover text-pastel-subtext"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleResetZoom}
            aria-label="Reset zoom"
            className="p-1 rounded hover:bg-pastel-hover text-pastel-subtext border-l border-pastel-border"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Canvas Area */}
      <div className="flex-1 overflow-auto p-6 bg-pastel-bg/40 flex justify-center">
        <div
          className="w-full max-w-3xl bg-white border border-pastel-border rounded-xl shadow-pastel p-8 relative transition-transform duration-150"
          style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
        >
          {/* Render Units */}
          <div className="space-y-4">
            {units.map((unit) => {
              const unitFindings = findingByUnit[unit.unit_id] || [];
              const isUnitSelected = unitFindings.some((f) => f.finding_id === selectedFindingId);

              // 1. Image unit with Responsive SVG Bounding-Box Overlay
              if (unit.kind === "image") {
                return (
                  <div
                    key={unit.unit_id}
                    className={`relative rounded-xl border overflow-hidden transition-all ${
                      isUnitSelected
                        ? "border-pastel-rose-border ring-2 ring-pastel-rose-border bg-pastel-rose-bg/20"
                        : "border-pastel-border bg-pastel-bg"
                    }`}
                  >
                    {/* Simulated banner/graphic image */}
                    <div className="w-full h-48 bg-gradient-to-r from-pastel-blue-bg via-pastel-indigo-bg to-pastel-purple-bg flex items-center justify-center relative">
                      <div className="text-center p-4">
                        <ImageIcon className="w-8 h-8 text-pastel-indigo-text mx-auto mb-2 opacity-80" />
                        <p className="text-sm font-bold text-pastel-indigo-text">{unit.text}</p>
                        <p className="text-xs text-pastel-muted mt-1">{unit.alt_text}</p>
                      </div>

                      {/* Responsive SVG Bounding Box Overlay using relative coordinates (viewBox 0 0 1 1) */}
                      {unit.bbox && (
                        <>
                          <svg
                            viewBox="0 0 1 1"
                            preserveAspectRatio="none"
                            className="absolute inset-0 w-full h-full pointer-events-auto"
                            aria-label="Visual accessibility bounding box overlay"
                          >
                            {unitFindings.map((f) => {
                              const isFSelected = f.finding_id === selectedFindingId;
                              const [, x0, y0, x1, y1] = unit.bbox!;
                              const w = Math.max(x1 - x0, 0.05);
                              const h = Math.max(y1 - y0, 0.05);

                              return (
                                <g
                                  key={f.finding_id}
                                  className="cursor-pointer group"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    if (onSelectFinding) onSelectFinding(f.finding_id);
                                  }}
                                >
                                  <rect
                                    x={x0}
                                    y={y0}
                                    width={w}
                                    height={h}
                                    rx={0.015}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      if (onSelectFinding) onSelectFinding(f.finding_id);
                                    }}
                                    className={`transition-all ${
                                      isFSelected
                                        ? "fill-pastel-rose-badge/50 stroke-pastel-rose-text stroke-[0.01] animate-pulse"
                                        : "fill-pastel-amber-badge/30 stroke-pastel-amber-text stroke-[0.006] hover:fill-pastel-amber-badge/50"
                                    }`}
                                  />
                                  <text
                                    x={x0 + 0.02}
                                    y={y0 + 0.06}
                                    fontSize="0.04"
                                    className="fill-pastel-text font-mono font-bold select-none pointer-events-none"
                                  >
                                    {f.type.toUpperCase()}
                                  </text>
                                </g>
                              );
                            })}
                          </svg>

                          {/* Keyboard Accessible Bounding-Box Overlay Buttons */}
                          <div className="absolute inset-0 pointer-events-none">
                            {unitFindings.map((f) => (
                              <button
                                key={`btn-${f.finding_id}`}
                                type="button"
                                aria-label={`Select bounding box for ${f.type} finding`}
                                onClick={() => onSelectFinding && onSelectFinding(f.finding_id)}
                                className="sr-only pointer-events-auto focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-20 px-2 py-1 bg-white text-xs text-pastel-text rounded border border-pastel-border shadow-pastel"
                              >
                                Select finding {f.finding_id}
                              </button>
                            ))}
                          </div>
                        </>
                      )}
                    </div>

                    <div className="p-2 text-[11px] text-pastel-muted flex items-center justify-between border-t border-pastel-border bg-white">
                      <span>Image Unit: {unit.unit_id}</span>
                      <span>Coordinates: normalized [0.0 - 1.0]</span>
                    </div>
                  </div>
                );
              }

              // 2. Heading or Text Units with Highlight Fallback
              const hasFindings = unitFindings.length > 0;

              return (
                <div
                  key={unit.unit_id}
                  className={`p-3 rounded-lg transition-all relative ${
                    isUnitSelected
                      ? "bg-pastel-indigo-bg/40 border border-pastel-indigo-border ring-2 ring-pastel-indigo-border"
                      : hasFindings
                      ? "bg-pastel-bg/40 border border-pastel-border hover:bg-pastel-hover/50"
                      : "hover:bg-pastel-hover/30"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1 text-[10px] text-pastel-muted">
                    <span className="font-mono">{unit.unit_id}</span>
                    {hasFindings && (
                      <span className="font-semibold text-pastel-rose-text flex items-center gap-1">
                        ● {unitFindings.length} issue{unitFindings.length === 1 ? "" : "s"}
                      </span>
                    )}
                  </div>

                  {/* Text Rendering with precise span or block-level highlight */}
                  <div className={`text-sm leading-relaxed ${unit.kind === "heading" ? "font-bold text-base text-pastel-text" : "text-pastel-text"}`}>
                    <HighlightedUnitText
                      unit={unit}
                      findings={unitFindings}
                      selectedFindingId={selectedFindingId}
                      onSelectFinding={onSelectFinding}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

// Sub-component to safely render highlighted text spans with block fallback
interface HighlightedUnitTextProps {
  unit: ContentUnit;
  findings: Finding[];
  selectedFindingId?: string | null;
  onSelectFinding?: (findingId: string) => void;
}

function HighlightedUnitText({
  unit,
  findings,
  selectedFindingId,
  onSelectFinding,
}: HighlightedUnitTextProps) {
  if (findings.length === 0) {
    return <span>{unit.text}</span>;
  }

  const text = unit.text;

  // Find if a specific finding matches a quote inside this unit
  const activeFinding = findings.find((f) => f.finding_id === selectedFindingId) || findings[0];
  const quote = activeFinding.span.quote;
  const quoteIndex = text.indexOf(quote);

  // Fallback: When character offsets split across DOCX runs or verbatim match is missing,
  // highlight the entire block cleanly (unit_id fallback per PRD §4.2 Y-19)
  if (quoteIndex === -1) {
    return (
      <mark
        onClick={() => onSelectFinding && onSelectFinding(activeFinding.finding_id)}
        className="bg-pastel-rose-badge text-pastel-text border-b-2 border-pastel-rose-text px-1 py-0.5 rounded cursor-pointer transition-all hover:bg-pastel-rose-border block"
      >
        {text}
      </mark>
    );
  }

  // Precise text span highlight
  const before = text.slice(0, quoteIndex);
  const match = text.slice(quoteIndex, quoteIndex + quote.length);
  const after = text.slice(quoteIndex + quote.length);
  const isSelected = activeFinding.finding_id === selectedFindingId;

  return (
    <span>
      {before}
      <mark
        onClick={(e) => {
          e.stopPropagation();
          if (onSelectFinding) onSelectFinding(activeFinding.finding_id);
        }}
        className={`px-1 py-0.5 rounded font-medium cursor-pointer transition-all border-b-2 ${
          isSelected
            ? "bg-pastel-rose-badge text-pastel-rose-text border-pastel-rose-text ring-2 ring-pastel-rose-border font-bold"
            : "bg-pastel-amber-badge text-pastel-amber-text border-pastel-amber-text hover:bg-pastel-amber-border"
        }`}
      >
        {match}
      </mark>
      {after}
    </span>
  );
}
