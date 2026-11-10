import React, { useState } from "react";
import { IntentCard } from "../../types";
import { Compass, Sparkles, ChevronDown, ChevronUp, RefreshCw, Check } from "lucide-react";

interface IntentCardDrawerProps {
  intentCard: IntentCard;
  onSaveIntentCard: (updated: IntentCard) => void;
  onRerunConstrainedFixes?: () => void;
}

export function IntentCardDrawer({
  intentCard,
  onSaveIntentCard,
  onRerunConstrainedFixes,
}: IntentCardDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [purpose, setPurpose] = useState(intentCard.purpose);
  const [audience, setAudience] = useState(intentCard.audience);
  const [keyMessage, setKeyMessage] = useState(intentCard.key_message);
  const [cta, setCta] = useState(intentCard.cta);
  const [isSaved, setIsSaved] = useState(false);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    onSaveIntentCard({
      purpose,
      audience,
      key_message: keyMessage,
      cta,
    });
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 2000);
    if (onRerunConstrainedFixes) {
      onRerunConstrainedFixes();
    }
  };

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white shadow-sm overflow-hidden hover:shadow-md transition-shadow duration-200">
      {/* Drawer Toggle Bar */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full text-left p-5 flex items-start justify-between gap-3 bg-white hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-start gap-3">
          <div className="p-2 rounded-xl bg-violet-50 text-violet-600 mt-0.5 flex-shrink-0">
            <Compass className="w-5 h-5" />
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-sm font-bold text-slate-900">Intent Card (Constrained Fixes)</h3>
              <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-violet-50 text-violet-700 border border-violet-200/80 flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-violet-500" />
                Auto-extracted
              </span>
            </div>
            {/* Purpose and Audience naturally formatted with zero truncation cutoffs */}
            <div className="text-xs text-slate-600 space-y-0.5">
              <p><span className="font-semibold text-slate-700">Purpose:</span> {purpose}</p>
              <p><span className="font-semibold text-slate-700">Audience:</span> {audience}</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 text-slate-500 flex-shrink-0 pt-1">
          <span className="text-xs font-medium hidden sm:inline text-slate-500">
            {isOpen ? "Collapse" : "Edit constraints"}
          </span>
          <div className="p-1 rounded-lg bg-slate-100 text-slate-600">
            {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </div>
        </div>
      </button>

      {/* Collapsible Content */}
      {isOpen && (
        <form onSubmit={handleSave} className="p-5 bg-slate-50/50 border-t border-slate-100 space-y-4">
          <p className="text-xs text-slate-600 leading-relaxed bg-white p-3 rounded-xl border border-slate-200/80">
            The Intent Card guides LLM fix generation to preserve core tone, persona, and value propositions while eliminating guideline violations.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            <div>
              <label htmlFor="intent-purpose" className="block text-xs font-semibold text-slate-700 mb-1.5">
                Content Purpose
              </label>
              <input
                id="intent-purpose"
                type="text"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="e.g. Q1 Enterprise Growth Campaign"
                className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
              />
            </div>

            <div>
              <label htmlFor="intent-audience" className="block text-xs font-semibold text-slate-700 mb-1.5">
                Target Audience
              </label>
              <input
                id="intent-audience"
                type="text"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g. Enterprise Security Officers"
                className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
              />
            </div>
          </div>

          <div>
            <label htmlFor="intent-key-message" className="block text-xs font-semibold text-slate-700 mb-1.5">
              Core Value Proposition / Key Message
            </label>
            <input
              id="intent-key-message"
              type="text"
              value={keyMessage}
              onChange={(e) => setKeyMessage(e.target.value)}
              placeholder="e.g. 99.95% high availability across our customer base"
              className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
            />
          </div>

          <div>
            <label htmlFor="intent-cta" className="block text-xs font-semibold text-slate-700 mb-1.5">
              Call To Action (CTA)
            </label>
            <input
              id="intent-cta"
              type="text"
              value={cta}
              onChange={(e) => setCta(e.target.value)}
              placeholder="e.g. Schedule an enterprise compliance demo"
              className="w-full text-xs px-3.5 py-2 rounded-xl border border-slate-300 bg-white text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 outline-none shadow-sm"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2">
            <button
              type="submit"
              className="py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold text-xs shadow-sm shadow-indigo-200 flex items-center gap-1.5 transition-all"
            >
              {isSaved ? <Check className="w-3.5 h-3.5 text-white" /> : <RefreshCw className="w-3.5 h-3.5" />}
              {isSaved ? "Saved & Applied" : "Save & Re-run Constrained Fixes (T9)"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
