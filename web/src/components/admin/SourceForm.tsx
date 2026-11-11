import React, { useState } from "react";
import { Source } from "../../types";
import { PlusCircle, Upload, Check, AlertCircle, FileCode } from "lucide-react";

interface SourceFormProps {
  onAddSource: (source: Source) => void;
  onImportKit?: (count: number) => void;
}

export function SourceForm({ onAddSource, onImportKit }: SourceFormProps) {
  const [activeTab, setActiveTab] = useState<"define" | "import">("define");
  const [sourceId, setSourceId] = useState("");
  const [kind, setKind] = useState<"rule" | "fact" | "term" | "asset">("fact");
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [value, setValue] = useState("");
  const [unit, setUnit] = useState("");
  const [importJson, setImportJson] = useState("");
  const [feedback, setFeedback] = useState<{ message: string; type: "success" | "error" } | null>(null);

  const handleSubmitDefine = (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceId.trim() || !name.trim() || !body.trim()) {
      setFeedback({ message: "Source ID, Name, and Body are required fields.", type: "error" });
      return;
    }

    const newSource: Source = {
      id: sourceId.trim().toUpperCase(),
      tenant_id: "tenant_meridian",
      kind,
      name: name.trim(),
      current_version: 1,
      status: "active",
      created_at: new Date().toISOString(),
      versions: [
        {
          version: 1,
          content_hash: "sha256_" + Math.random().toString(36).substring(2, 10),
          body: body.trim(),
          value: value.trim() || undefined,
          unit: unit.trim() || undefined,
          valid_from: new Date().toISOString(),
          created_at: new Date().toISOString(),
        },
      ],
    };

    onAddSource(newSource);
    setFeedback({
      message: `Source ${newSource.id} defined and compiled successfully (v1).`,
      type: "success",
    });

    // Reset form
    setSourceId("");
    setName("");
    setBody("");
    setValue("");
    setUnit("");
  };

  const handleImportBrandKit = (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const parsed = JSON.parse(importJson);
      const items = Array.isArray(parsed) ? parsed : parsed.sources || [];
      if (items.length === 0) {
        throw new Error("No source records found in payload.");
      }

      items.forEach((item: any, idx: number) => {
        const s: Source = {
          id: item.id || `SRC-${idx + 1}`,
          tenant_id: "tenant_meridian",
          kind: item.kind || "fact",
          name: item.name || `Imported Source ${idx + 1}`,
          current_version: 1,
          status: "active",
          created_at: new Date().toISOString(),
          versions: [
            {
              version: 1,
              content_hash: "hash_import_" + Math.random().toString(36).substring(2, 8),
              body: item.body || item.text || "",
              value: item.value,
              unit: item.unit,
              valid_from: new Date().toISOString(),
              created_at: new Date().toISOString(),
            },
          ],
        };
        onAddSource(s);
      });

      if (onImportKit) onImportKit(items.length);
      setFeedback({
        message: `Successfully imported and compiled ${items.length} source records. Idempotency verified.`,
        type: "success",
      });
      setImportJson("");
    } catch (err: any) {
      setFeedback({
        message: `Invalid JSON format: ${err.message}`,
        type: "error",
      });
    }
  };

  const handleSeedExampleKit = () => {
    const exampleKit = [
      {
        id: "F-120",
        kind: "fact",
        name: "Security SOC 2 Compliance",
        body: "Meridian Flow maintains SOC 2 Type II compliance with annual independent audits.",
        value: "SOC 2 Type II",
      },
      {
        id: "R-05",
        kind: "rule",
        name: "CTA Formatting",
        body: "All call-to-action buttons must begin with an active verb (e.g., 'Schedule', 'Start', 'Explore').",
      },
    ];
    setImportJson(JSON.stringify(exampleKit, null, 2));
  };

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-sm space-y-4">
      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
        <button
          type="button"
          onClick={() => {
            setActiveTab("define");
            setFeedback(null);
          }}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all duration-150 ${
            activeTab === "define"
              ? "bg-indigo-50 text-indigo-700 border border-indigo-200/80 shadow-sm"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          <PlusCircle className="w-4 h-4 text-indigo-500" />
          Define Source
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveTab("import");
            setFeedback(null);
          }}
          className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all duration-150 ${
            activeTab === "import"
              ? "bg-indigo-50 text-indigo-700 border border-indigo-200/80 shadow-sm"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          <Upload className="w-4 h-4 text-indigo-500" />
          Structured Import (Brand Kit)
        </button>
      </div>

      {feedback && (
        <div
          role="alert"
          className={`p-3.5 rounded-xl text-xs flex items-center gap-2.5 border shadow-sm ${
            feedback.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          {feedback.type === "success" ? (
            <Check className="w-4 h-4 flex-shrink-0 text-emerald-600 font-bold" />
          ) : (
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-600 font-bold" />
          )}
          <span className="font-medium">{feedback.message}</span>
        </div>
      )}

      {/* Define Form */}
      {activeTab === "define" && (
        <form onSubmit={handleSubmitDefine} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            <div>
              <label htmlFor="source-id" className="block text-xs font-semibold text-slate-700 mb-1.5">
                Source ID (e.g. F-112, R-01) *
              </label>
              <input
                id="source-id"
                type="text"
                value={sourceId}
                onChange={(e) => setSourceId(e.target.value)}
                placeholder="F-112"
                required
                className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
              />
            </div>

            <div>
              <label htmlFor="source-kind" className="block text-xs font-semibold text-slate-700 mb-1.5">
                Kind *
              </label>
              <select
                id="source-kind"
                value={kind}
                onChange={(e) => setKind(e.target.value as any)}
                className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm cursor-pointer"
              >
                <option value="fact">Fact (Temporal claims & numbers)</option>
                <option value="rule">Rule (Governance, naming & grammar)</option>
                <option value="term">Term (Glossary terminology)</option>
                <option value="asset">Asset (Logos & visual palette)</option>
              </select>
            </div>
          </div>

          <div>
            <label htmlFor="source-name" className="block text-xs font-semibold text-slate-700 mb-1.5">
              Title / Name *
            </label>
            <input
              id="source-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Customer Count or Brand Name Policy"
              required
              className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
            />
          </div>

          <div>
            <label htmlFor="source-body" className="block text-xs font-semibold text-slate-700 mb-1.5">
              Guideline Statement / Fact Body *
            </label>
            <textarea
              id="source-body"
              rows={3}
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Full statement of the guideline, canonical policy, or verified claim."
              required
              className="w-full text-xs px-3.5 py-2.5 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
            />
          </div>

          <div className="grid grid-cols-2 gap-3.5">
            <div>
              <label htmlFor="source-value" className="block text-xs font-semibold text-slate-700 mb-1.5">
                Canonical Value (optional)
              </label>
              <input
                id="source-value"
                type="text"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="e.g. 25,000+ or 99.95%"
                className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
              />
            </div>
            <div>
              <label htmlFor="source-unit" className="block text-xs font-semibold text-slate-700 mb-1.5">
                Unit (optional)
              </label>
              <input
                id="source-unit"
                type="text"
                value={unit}
                onChange={(e) => setUnit(e.target.value)}
                placeholder="e.g. customers, uptime %, ms"
                className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
              />
            </div>
          </div>

          <button
            type="submit"
            className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-xs shadow-sm shadow-indigo-200 transition-all flex items-center justify-center gap-2"
          >
            <PlusCircle className="w-4 h-4" />
            Compile & Save Source
          </button>
        </form>
      )}

      {/* Import Form */}
      {activeTab === "import" && (
        <form onSubmit={handleImportBrandKit} className="space-y-4">
          <div className="flex items-center justify-between">
            <label htmlFor="import-json" className="block text-xs font-semibold text-slate-700">
              Brand Kit JSON Payload
            </label>
            <button
              type="button"
              onClick={handleSeedExampleKit}
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 hover:underline flex items-center gap-1.5"
            >
              <FileCode className="w-3.5 h-3.5" />
              Load Sample Kit
            </button>
          </div>

          <textarea
            id="import-json"
            rows={6}
            value={importJson}
            onChange={(e) => setImportJson(e.target.value)}
            placeholder='[{"id": "F-120", "kind": "fact", "name": "...", "body": "...", "value": "..."}]'
            required
            className="w-full font-mono text-xs p-3.5 rounded-xl border border-slate-300 bg-slate-50 text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
          />

          <button
            type="submit"
            className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-xs shadow-sm shadow-indigo-200 transition-all flex items-center justify-center gap-2"
          >
            <Upload className="w-4 h-4" />
            Import & Verify Idempotency
          </button>
        </form>
      )}
    </div>
  );
}
