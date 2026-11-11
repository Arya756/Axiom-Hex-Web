import React, { useState } from "react";
import { SensitivityLevel, ReviewRunProgress } from "../../types";
import { UploadCloud, FileText, Shield, Loader2, CheckCircle2, AlertTriangle, Sparkles, Check } from "lucide-react";

interface UploadDrawerProps {
  onUploadSuccess: (file: File, sensitivity: SensitivityLevel) => void;
  runProgress?: ReviewRunProgress | null;
}

export function UploadDrawer({ onUploadSuccess, runProgress }: UploadDrawerProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityLevel>("internal");
  const [isDragging, setIsDragging] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const allowedExtensions = [".md", ".txt", ".pdf", ".docx", ".png", ".jpg", ".jpeg"];

  const selectValidatedFile = (file: File) => {
    const lower = file.name.toLowerCase();
    const isAllowed = allowedExtensions.some((ext) => lower.endsWith(ext));
    if (!isAllowed) {
      setUploadError(
        `Unsupported file type for "${file.name}". Allowed formats: ${allowedExtensions.join(", ")}.`
      );
      setSelectedFile(null);
      return;
    }
    setUploadError(null);
    setSelectedFile(file);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      selectValidatedFile(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      selectValidatedFile(e.dataTransfer.files[0]);
    }
  };

  const handleTriggerUpload = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError("Please select a supported draft file before starting the pre-check.");
      return;
    }
    setUploadError(null);
    onUploadSuccess(selectedFile, sensitivity);
  };

  const sensitivityLabels: Record<
    SensitivityLevel,
    { title: string; desc: string; badge: string; colorClass: string }
  > = {
    public: {
      title: "Public",
      desc: "Marketing & external website materials",
      badge: "Standard",
      colorClass: "border-sky-300 bg-sky-50/60 text-sky-900 ring-sky-500",
    },
    internal: {
      title: "Internal",
      desc: "Standard internal company docs & planning",
      badge: "Default",
      colorClass: "border-indigo-300 bg-indigo-50/60 text-indigo-900 ring-indigo-500",
    },
    confidential: {
      title: "Confidential",
      desc: "NDA-gated enterprise strategy & pricing",
      badge: "High",
      colorClass: "border-amber-300 bg-amber-50/60 text-amber-900 ring-amber-500",
    },
    restricted: {
      title: "Restricted",
      desc: "Strictly deterministic checks: 0 external API calls",
      badge: "Isolated",
      colorClass: "border-rose-300 bg-rose-50/60 text-rose-900 ring-rose-500",
    },
  };

  const isRunning = Boolean(runProgress && runProgress.status === "running");

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-sm hover:shadow-md transition-shadow duration-200 space-y-4">
      <div className="flex items-center justify-between border-b border-slate-100 pb-3">
        <div className="flex items-center gap-2.5">
          <div className="p-2 rounded-xl bg-indigo-50 text-indigo-600">
            <UploadCloud className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-bold text-slate-900">Draft Upload & Sensitivity Scoping</h2>
            <p className="text-xs text-slate-500">Ingest Markdown, PDF, DOCX, or graphic banners</p>
          </div>
        </div>
        <span className="text-[11px] font-medium text-slate-500 bg-slate-100 px-2.5 py-1 rounded-full border border-slate-200">
          .md, .txt, .pdf, .docx, .png, .jpg
        </span>
      </div>

      <form onSubmit={handleTriggerUpload} className="space-y-3.5">
        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-4 text-center transition-all duration-200 cursor-pointer ${
            isDragging
              ? "border-indigo-500 bg-indigo-50/80 scale-[1.01]"
              : selectedFile
              ? "border-emerald-400 bg-emerald-50/40"
              : "border-slate-200 bg-slate-50/60 hover:bg-slate-50 hover:border-slate-300"
          }`}
        >
          <input
            type="file"
            id="file-upload-input"
            onChange={handleFileChange}
            accept=".md,.txt,.pdf,.docx,.png,.jpg,.jpeg"
            className="sr-only"
          />
          <label htmlFor="file-upload-input" className="cursor-pointer block space-y-1.5">
            <div
              className={`w-10 h-10 rounded-xl mx-auto flex items-center justify-center transition-all ${
                selectedFile
                  ? "bg-emerald-100 text-emerald-700 shadow-sm"
                  : "bg-white text-indigo-600 shadow-sm border border-slate-200"
              }`}
            >
              {selectedFile ? (
                <FileText className="w-5 h-5" />
              ) : (
                <UploadCloud className="w-5 h-5" />
              )}
            </div>
            {selectedFile ? (
              <div className="space-y-0.5">
                <p className="text-xs font-semibold text-slate-900">{selectedFile.name}</p>
                <p className="text-[11px] text-emerald-700 font-medium">
                  {(selectedFile.size / 1024).toFixed(1)} KB · Ready to review
                </p>
              </div>
            ) : (
              <div>
                <p className="text-xs font-medium text-slate-700">
                  <span className="font-semibold text-indigo-600 hover:text-indigo-700 underline underline-offset-2">Click to select file</span> or drag and drop
                </p>
                <p className="text-[11px] text-slate-500">Auto-tokenized into content units and verified</p>
              </div>
            )}
          </label>
        </div>

        {/* Sensitivity Scoping */}
        <div className="space-y-1.5">
          <label className="block text-xs font-semibold text-slate-700 flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-indigo-600" />
            Sensitivity Policy:
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" role="radiogroup" aria-label="Sensitivity selection">
            {(Object.keys(sensitivityLabels) as SensitivityLevel[]).map((level) => {
              const info = sensitivityLabels[level];
              const isSelected = sensitivity === level;
              return (
                <button
                  key={level}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => setSensitivity(level)}
                  className={`p-2.5 rounded-xl border text-left transition-all duration-150 flex flex-col justify-between ${
                    isSelected
                      ? `border-indigo-500 bg-indigo-50/70 shadow-sm ring-2 ring-indigo-500/20 text-indigo-950`
                      : "border-slate-200 bg-white hover:bg-slate-50 hover:border-slate-300 text-slate-600"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1 w-full">
                    <span className="text-xs font-bold text-slate-900 capitalize flex items-center gap-1">
                      {info.title}
                    </span>
                    {isSelected && <Check className="w-3.5 h-3.5 text-indigo-600 font-bold" />}
                  </div>
                  <p className="text-[10px] text-slate-500 leading-snug">{info.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Explicit Error State Alert */}
        {uploadError && (
          <div
            role="alert"
            className="rounded-xl border border-rose-200 bg-rose-50/90 px-3.5 py-2.5 text-xs text-rose-900 flex items-center gap-2 shadow-2xs"
          >
            <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" aria-hidden="true" />
            <span className="font-medium">{uploadError}</span>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={!selectedFile || isRunning}
          className={`w-full py-2.5 px-4 rounded-xl font-semibold text-xs flex items-center justify-center gap-2 shadow-sm transition-all duration-150 ${
            !selectedFile || isRunning
              ? "bg-slate-100 text-slate-400 border border-slate-200 cursor-not-allowed"
              : "bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white shadow-indigo-200"
          }`}
        >
          {isRunning ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-indigo-200" />
              Running Multi-Agent Pre-Check ({runProgress?.progress}%)...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Upload & Run Automated Pre-Check
            </>
          )}
        </button>
      </form>

      {/* Run Progress Telemetry - without cutoffs */}
      {runProgress && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-xl border border-slate-200 bg-slate-50/80 p-3 space-y-2"
        >
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-slate-900 flex items-center gap-2">
              {runProgress.status === "running" && <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />}
              {runProgress.status === "done" && <CheckCircle2 className="w-4 h-4 text-emerald-600" />}
              {runProgress.status === "partial" && <AlertTriangle className="w-4 h-4 text-amber-600" />}
              Review Run: {runProgress.status.toUpperCase()}
            </span>
            <span className="font-mono text-xs font-bold text-slate-700 bg-white px-2 py-0.5 rounded border border-slate-200">
              {runProgress.progress}%
            </span>
          </div>

          <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden shadow-inner">
            <div
              className={`h-full transition-all duration-300 rounded-full ${
                runProgress.status === "failed"
                  ? "bg-rose-600"
                  : runProgress.status === "partial"
                  ? "bg-amber-500"
                  : "bg-indigo-600"
              }`}
              style={{ width: `${runProgress.progress}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-xs text-slate-600 pt-0.5 gap-2 flex-wrap">
            <span>Step: <span className="font-medium text-slate-800">{runProgress.active_step || "Checkers completed"}</span></span>
            <span className="font-semibold text-slate-900 flex-shrink-0">
              {runProgress.findings_count} finding{runProgress.findings_count === 1 ? "" : "s"} identified
              {runProgress.cached && " (Cache hit)"}
            </span>
          </div>
          {runProgress.status === "failed" && (
            <div
              role="alert"
              className="mt-1 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-900 flex items-center gap-2"
            >
              <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0" aria-hidden="true" />
              <span>Pre-check run failed or encountered an unreadable input. Please check format and retry.</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
