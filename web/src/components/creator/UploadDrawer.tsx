import React, { useState } from "react";
import { SensitivityLevel, ReviewRunProgress } from "../../types";
import { UploadCloud, FileText, Shield, Loader2, CheckCircle2, AlertTriangle, Sparkles } from "lucide-react";

interface UploadDrawerProps {
  onUploadSuccess: (file: File, sensitivity: SensitivityLevel) => void;
  runProgress?: ReviewRunProgress | null;
}

export function UploadDrawer({ onUploadSuccess, runProgress }: UploadDrawerProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityLevel>("internal");
  const [isDragging, setIsDragging] = useState(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleTriggerUpload = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) return;
    onUploadSuccess(selectedFile, sensitivity);
  };

  const sensitivityLabels: Record<SensitivityLevel, { title: string; desc: string; badgeClass: string }> = {
    public: {
      title: "Public",
      desc: "Marketing & external website materials",
      badgeClass: "bg-pastel-blue-badge text-pastel-blue-text border-pastel-blue-border",
    },
    internal: {
      title: "Internal",
      desc: "Standard internal company docs & planning",
      badgeClass: "bg-pastel-indigo-badge text-pastel-indigo-text border-pastel-indigo-border",
    },
    confidential: {
      title: "Confidential",
      desc: "NDA-gated enterprise strategy & pricing",
      badgeClass: "bg-pastel-amber-badge text-pastel-amber-text border-pastel-amber-border",
    },
    restricted: {
      title: "Restricted",
      desc: "Strictly deterministic checks: 0 external API calls",
      badgeClass: "bg-pastel-rose-badge text-pastel-rose-text border-pastel-rose-border",
    },
  };

  return (
    <div className="rounded-xl border border-pastel-border bg-pastel-card p-5 shadow-pastel space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-pastel-text flex items-center gap-1.5">
          <UploadCloud className="w-4 h-4 text-pastel-indigo-text" />
          Draft Upload & Sensitivity Scoping
        </h2>
        <span className="text-xs text-pastel-muted">Accepts .md, .txt, .pdf, .docx, .png, .jpg</span>
      </div>

      <form onSubmit={handleTriggerUpload} className="space-y-4">
        {/* Dropzone */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`border-2 border-dashed rounded-xl p-5 text-center transition-all ${
            isDragging
              ? "border-pastel-indigo-text bg-pastel-indigo-bg/60"
              : selectedFile
              ? "border-pastel-green-border bg-pastel-green-bg/40"
              : "border-pastel-border bg-pastel-bg/60 hover:bg-pastel-hover/60"
          }`}
        >
          <input
            type="file"
            id="file-upload-input"
            onChange={handleFileChange}
            accept=".md,.txt,.pdf,.docx,.png,.jpg,.jpeg"
            className="sr-only"
          />
          <label htmlFor="file-upload-input" className="cursor-pointer block space-y-2">
            <div className="w-10 h-10 rounded-full bg-white mx-auto flex items-center justify-center shadow-pastel border border-pastel-border">
              {selectedFile ? (
                <FileText className="w-5 h-5 text-pastel-green-text" />
              ) : (
                <UploadCloud className="w-5 h-5 text-pastel-indigo-text" />
              )}
            </div>
            {selectedFile ? (
              <div>
                <p className="text-xs font-semibold text-pastel-text">{selectedFile.name}</p>
                <p className="text-[11px] text-pastel-muted">
                  {(selectedFile.size / 1024).toFixed(1)} KB · Ready to review
                </p>
              </div>
            ) : (
              <div>
                <p className="text-xs font-medium text-pastel-text">
                  <span className="font-semibold text-pastel-indigo-text hover:underline">Click to upload</span> or drag and drop
                </p>
                <p className="text-[11px] text-pastel-muted">Markdown, PDF text layer, DOCX, or visual banners</p>
              </div>
            )}
          </label>
        </div>

        {/* Sensitivity Scoping */}
        <div>
          <label className="block text-xs font-semibold text-pastel-text mb-2 flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5 text-pastel-indigo-text" />
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
                  className={`p-2.5 rounded-lg border text-left transition-all ${
                    isSelected
                      ? `border-pastel-indigo-border bg-pastel-indigo-bg shadow-pastel ring-1 ring-pastel-indigo-border`
                      : "border-pastel-border bg-pastel-card hover:bg-pastel-hover text-pastel-subtext"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-bold text-pastel-text capitalize">{info.title}</span>
                  </div>
                  <p className="text-[10px] text-pastel-muted leading-tight">{info.desc}</p>
                </button>
              );
            })}
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={!selectedFile || Boolean(runProgress && runProgress.status === "running")}
          className={`w-full py-2.5 px-4 rounded-lg font-semibold text-xs flex items-center justify-center gap-2 shadow-pastel transition-all ${
            !selectedFile || Boolean(runProgress && runProgress.status === "running")
              ? "bg-pastel-border text-pastel-muted cursor-not-allowed"
              : "bg-pastel-indigo-badge hover:bg-pastel-indigo-border text-pastel-indigo-text border border-pastel-indigo-border"
          }`}
        >
          {runProgress && runProgress.status === "running" ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-pastel-indigo-text" />
              Running Multi-Agent Pre-Check ({runProgress.progress}%)...
            </>
          ) : (
            <>
              <Sparkles className="w-4 h-4" />
              Upload & Run Automated Pre-Check
            </>
          )}
        </button>
      </form>

      {/* Run Progress Telemetry */}
      {runProgress && (
        <div
          role="status"
          aria-live="polite"
          className="rounded-lg border border-pastel-border bg-pastel-bg p-3 space-y-2"
        >
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-pastel-text flex items-center gap-1.5">
              {runProgress.status === "running" && <Loader2 className="w-3.5 h-3.5 animate-spin text-pastel-indigo-text" />}
              {runProgress.status === "done" && <CheckCircle2 className="w-3.5 h-3.5 text-pastel-green-text" />}
              {runProgress.status === "partial" && <AlertTriangle className="w-3.5 h-3.5 text-pastel-amber-text" />}
              Review Run: {runProgress.status.toUpperCase()}
            </span>
            <span className="font-mono text-[11px] text-pastel-muted">{runProgress.progress}%</span>
          </div>

          <div className="w-full bg-pastel-border rounded-full h-1.5 overflow-hidden">
            <div
              className={`h-full transition-all duration-300 ${
                runProgress.status === "failed"
                  ? "bg-pastel-rose-text"
                  : runProgress.status === "partial"
                  ? "bg-pastel-amber-text"
                  : "bg-pastel-indigo-text"
              }`}
              style={{ width: `${runProgress.progress}%` }}
            />
          </div>

          <div className="flex items-center justify-between text-[11px] text-pastel-subtext pt-0.5">
            <span>Step: {runProgress.active_step || "Checkers completed"}</span>
            <span className="font-medium text-pastel-text">
              {runProgress.findings_count} finding{runProgress.findings_count === 1 ? "" : "s"} identified
              {runProgress.cached && " (Cache hit)"}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
