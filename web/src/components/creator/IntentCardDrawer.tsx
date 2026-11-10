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
    <div className="rounded-xl border border-pastel-indigo-border bg-pastel-card shadow-pastel transition-all overflow-hidden">
      {/* Drawer Toggle Bar */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full text-left p-4 flex items-center justify-between gap-3 bg-pastel-indigo-bg/50 hover:bg-pastel-indigo-bg transition-colors"
      >
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-pastel-indigo-badge text-pastel-indigo-text">
            <Compass className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-pastel-text">Intent Card (Constrained Fixes)</h3>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-pastel-indigo-badge text-pastel-indigo-text border border-pastel-indigo-border flex items-center gap-1">
                <Sparkles className="w-3 h-3" />
                Auto-extracted
              </span>
            </div>
            <p className="text-[11px] text-pastel-subtext mt-0.5 line-clamp-1">
              {purpose} · Audience: {audience}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-pastel-subtext">
          <span className="text-[11px] font-medium hidden sm:inline">
            {isOpen ? "Collapse drawer" : "Edit intent constraints"}
          </span>
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {/* Collapsible Content */}
      {isOpen && (
        <form onSubmit={handleSave} className="p-4 bg-pastel-card border-t border-pastel-border space-y-3">
          <p className="text-[11px] text-pastel-subtext">
            The Intent Card guides LLM fix generation to preserve core tone, persona, and value propositions while eliminating guideline violations.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="intent-purpose" className="block text-[11px] font-semibold text-pastel-text mb-1">
                Content Purpose
              </label>
              <input
                id="intent-purpose"
                type="text"
                value={purpose}
                onChange={(e) => setPurpose(e.target.value)}
                placeholder="e.g. Q1 Enterprise Growth Campaign"
                className="w-full text-xs px-3 py-1.5 rounded-lg border border-pastel-border bg-pastel-bg text-pastel-text focus:ring-2 focus:ring-pastel-indigo-border"
              />
            </div>

            <div>
              <label htmlFor="intent-audience" className="block text-[11px] font-semibold text-pastel-text mb-1">
                Target Audience
              </label>
              <input
                id="intent-audience"
                type="text"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                placeholder="e.g. Enterprise Security Officers"
                className="w-full text-xs px-3 py-1.5 rounded-lg border border-pastel-border bg-pastel-bg text-pastel-text focus:ring-2 focus:ring-pastel-indigo-border"
              />
            </div>
          </div>

          <div>
            <label htmlFor="intent-key-message" className="block text-[11px] font-semibold text-pastel-text mb-1">
              Core Value Proposition / Key Message
            </label>
            <input
              id="intent-key-message"
              type="text"
              value={keyMessage}
              onChange={(e) => setKeyMessage(e.target.value)}
              placeholder="e.g. 99.95% high availability across our customer base"
              className="w-full text-xs px-3 py-1.5 rounded-lg border border-pastel-border bg-pastel-bg text-pastel-text focus:ring-2 focus:ring-pastel-indigo-border"
            />
          </div>

          <div>
            <label htmlFor="intent-cta" className="block text-[11px] font-semibold text-pastel-text mb-1">
              Call To Action (CTA)
            </label>
            <input
              id="intent-cta"
              type="text"
              value={cta}
              onChange={(e) => setCta(e.target.value)}
              placeholder="e.g. Schedule an enterprise compliance demo"
              className="w-full text-xs px-3 py-1.5 rounded-lg border border-pastel-border bg-pastel-bg text-pastel-text focus:ring-2 focus:ring-pastel-indigo-border"
            />
          </div>

          <div className="pt-2 flex items-center justify-end gap-2">
            <button
              type="submit"
              className="py-1.5 px-3 rounded-lg bg-pastel-indigo-badge hover:bg-pastel-indigo-border text-pastel-indigo-text font-semibold text-xs border border-pastel-indigo-border shadow-pastel flex items-center gap-1.5 transition-all"
            >
              {isSaved ? <Check className="w-3.5 h-3.5 text-pastel-green-text" /> : <RefreshCw className="w-3.5 h-3.5" />}
              {isSaved ? "Saved & Applied" : "Save & Re-run Constrained Fixes (T9)"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}

