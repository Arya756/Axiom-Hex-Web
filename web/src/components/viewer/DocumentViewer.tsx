import React, { useState } from "react";
import { ContentUnit, Finding } from "../../types";
import { FileText, Image as ImageIcon, ZoomIn, ZoomOut, Maximize2, AlertCircle } from "lucide-react";

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
    <div className="rounded-2xl border border-slate-200/90 bg-white shadow-sm flex flex-col h-full overflow-hidden">
      {/* Viewer Toolbar */}
      <div className="px-5 py-3 bg-white border-b border-slate-200 flex items-center justify-between gap-3 text-xs flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="p-1.5 rounded-lg bg-indigo-50 text-indigo-600">
            <FileText className="w-4 h-4" />
          </div>
          <div>
            <span className="font-bold text-slate-800 capitalize text-sm">{fileType} Review Canvas</span>
            <span className="text-xs text-slate-500 font-medium ml-2">
              ({units.length} content units parsed)
            </span>
          </div>
        </div>

        {/* Zoom Controls */}
        <div className="flex items-center gap-1 bg-slate-100 border border-slate-200 rounded-xl p-1">
          <button
            type="button"
            onClick={handleZoomOut}
            aria-label="Zoom out"
            className="p-1.5 rounded-lg hover:bg-white text-slate-600 hover:text-slate-900 transition-colors"
          >
            <ZoomOut className="w-3.5 h-3.5" />
          </button>
          <span className="text-xs font-mono font-bold px-2 text-slate-700 min-w-[3rem] text-center select-none">
            {zoom}%
          </span>
          <button
            type="button"
            onClick={handleZoomIn}
            aria-label="Zoom in"
            className="p-1.5 rounded-lg hover:bg-white text-slate-600 hover:text-slate-900 transition-colors"
          >
            <ZoomIn className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={handleResetZoom}
            aria-label="Reset zoom"
            className="p-1.5 rounded-lg hover:bg-white text-slate-600 hover:text-slate-900 transition-colors border-l border-slate-200 ml-0.5"
          >
            <Maximize2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Canvas Area: clean light canvas with natural padding and internal scroll */}
      <div className="flex-1 overflow-auto p-4 sm:p-6 bg-slate-50/70">
        <div
          className="w-full bg-white border border-slate-200 rounded-2xl shadow-sm p-6 sm:p-8 space-y-5 transition-transform duration-150"
          style={{ transform: `scale(${zoom / 100})`, transformOrigin: "top center" }}
        >
          {units.map((unit) => {
            const unitFindings = findingByUnit[unit.unit_id] || [];
            const isUnitSelected = unitFindings.some((f) => f.finding_id === selectedFindingId);

            // 1. Image unit with Responsive SVG Bounding-Box Overlay
            if (unit.kind === "image") {
              return (
                <div
                  key={unit.unit_id}
                  className={`rounded-2xl border transition-all duration-200 overflow-hidden ${
                    isUnitSelected
                      ? "border-rose-400 ring-2 ring-rose-400/20 shadow-sm"
                      : "border-slate-200 bg-white"
                  }`}
                >
                  {/* Marketing Banner Container */}
                  <div className="relative bg-gradient-to-br from-indigo-50/80 via-slate-50 to-sky-50/60 p-6 rounded-t-2xl border-b border-slate-200">
                    {/* Top graphic header */}
                    <div className="flex items-center justify-between mb-4">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-sm">
                          <ImageIcon className="w-4 h-4" />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-slate-900 tracking-tight">Meridian Flow Platform</p>
                          <p className="text-[11px] text-slate-500">Visual Campaign Banner Asset</p>
                        </div>
                      </div>
                      <span className="text-[11px] font-semibold text-indigo-700 bg-indigo-100/70 px-2 py-0.5 rounded-full border border-indigo-200">
                        Image Unit: {unit.unit_id}
                      </span>
                    </div>

                    {/* Banner Graphic Area (relative canvas for SVG bounding box) */}
                    <div className="relative w-full h-44 rounded-xl border border-slate-300 bg-white shadow-inner overflow-hidden flex flex-col justify-between p-4">
                      <div className="space-y-1">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Primary Graphic Banner Layer
                        </span>
                        <p className="text-sm font-bold text-slate-800 leading-snug">{unit.text}</p>
                      </div>

                      {/* Promo callout text positioned in lower half corresponding to bbox [y: 0.48 to 0.78] */}
                      <div className="p-2.5 rounded-lg bg-sky-50 border border-sky-200 flex items-center justify-between text-xs">
                        <span className="text-sky-800 font-medium">
                          {unit.alt_text}
                        </span>
                        <span className="text-[10px] font-mono font-semibold text-sky-600 bg-white px-1.5 py-0.5 rounded border border-sky-200">
                          Contrast: 2.1:1 (Fails AA)
                        </span>
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
                                    rx={0.02}
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      if (onSelectFinding) onSelectFinding(f.finding_id);
                                    }}
                                    className={`transition-all ${
                                      isFSelected
                                        ? "fill-rose-500/15 stroke-rose-600 stroke-[0.012] animate-pulse"
                                        : "fill-amber-500/10 stroke-amber-600 stroke-[0.008] hover:fill-amber-500/20"
                                    }`}
                                  />
                                  <text
                                    x={x0 + 0.02}
                                    y={y0 + 0.05}
                                    fontSize="0.035"
                                    className="fill-slate-900 font-mono font-bold select-none pointer-events-none"
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
                                className="sr-only pointer-events-auto focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-20 px-3 py-1.5 bg-white text-xs font-semibold text-slate-800 rounded-lg border border-slate-300 shadow-md"
                              >
                                Select finding {f.finding_id}
                              </button>
                            ))}
                          </div>
                        </>
                      )}
                    </div>
                  </div>

                  <div className="p-3 bg-white text-xs text-slate-500 flex items-center justify-between">
                    <span className="flex items-center gap-1.5">
                      <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                      Visual WCAG Contrast Violation Detected
                    </span>
                    <span className="font-mono text-[11px] text-slate-400">
                      BBox: [1, 0.1, 0.48, 0.9, 0.78]
                    </span>
                  </div>
                </div>
              );
            }

            // 2. Heading or Text Units with Highlight Fallback
            const hasFindings = unitFindings.length > 0;

            return (
              <div
                key={unit.unit_id}
                className={`p-4 rounded-xl transition-all duration-150 relative ${
                  isUnitSelected
                    ? "bg-indigo-50/60 border border-indigo-200 ring-2 ring-indigo-500/20 shadow-sm"
                    : hasFindings
                    ? "bg-slate-50/70 border border-slate-200 hover:bg-slate-50"
                    : "hover:bg-slate-50/50 border border-transparent"
                }`}
              >
                <div className="flex items-center justify-between mb-2 text-xs text-slate-500">
                  <span className="font-mono font-semibold text-slate-600 bg-white px-2 py-0.5 rounded border border-slate-200 shadow-2xs">
                    {unit.unit_id}
                  </span>
                  {hasFindings && (
                    <span className="font-bold text-rose-700 bg-rose-50 px-2 py-0.5 rounded-full border border-rose-200 flex items-center gap-1">
                      ● {unitFindings.length} issue{unitFindings.length === 1 ? "" : "s"}
                    </span>
                  )}
                </div>

                {/* Text Rendering with precise span or block-level highlight */}
                <div
                  className={`leading-relaxed ${
                    unit.kind === "heading"
                      ? "font-bold text-lg text-slate-900 tracking-tight"
                      : "text-slate-800 text-sm"
                  }`}
                >
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
        className="bg-rose-100/90 text-slate-900 border-b-2 border-rose-500 px-1.5 py-0.5 rounded cursor-pointer transition-all hover:bg-rose-200 block font-medium shadow-2xs"
      >
        {text}
      </mark>
    );
  }

  // Precise text span highlight with clean padding and no descender clipping
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
        className={`px-1.5 py-0.5 rounded cursor-pointer transition-all border-b-2 inline font-medium ${
          isSelected
            ? "bg-rose-100 text-rose-950 border-rose-600 ring-2 ring-rose-200 font-bold shadow-2xs"
            : "bg-amber-100 text-amber-950 border-amber-500 hover:bg-amber-200"
        }`}
      >
        {match}
      </mark>
      {after}
    </span>
  );
}
