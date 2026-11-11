"""Citation Verifier for Axiom (PRD §4.3 A-11, I1.5, Gate G1/G2).

The anti-hallucination gate (upgraded to G2):
- Quote exists verbatim in the content unit.
- Character offsets are consistent with the quote.
- source_id@version resolves to a real knowledge-base record.
- Numbers parsed from quote and comparison recomputed (outdated / contradicted).
- Retrieval trace included in Unsupported finding explanation (G2).
- Failures are dropped and counted — never rendered as actionable findings.
- All shown findings pass the verifier (true by construction).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from brand_kit.fixtures import FACTS, GLOSSARY, RULES
from contracts.models import ContentUnit, Finding, FindingType, Method


class CitationVerifier:
    """Anti-hallucination verification gate for review findings (A-11, G2)."""

    def __init__(
        self,
        valid_source_ids: Optional[Set[str]] = None,
        valid_source_versions: Optional[Set[Tuple[str, int]]] = None,
    ) -> None:
        if valid_source_ids is not None:
            self.valid_source_ids = valid_source_ids
        else:
            self.valid_source_ids = set()
            self.valid_source_ids.update(r.rule_id for r in RULES)
            self.valid_source_ids.update(g.term_id for g in GLOSSARY)
            self.valid_source_ids.update(f.fact_id for f in FACTS)

        if valid_source_versions is not None:
            self.valid_source_versions = valid_source_versions
        else:
            self.valid_source_versions = set()
            for r in RULES:
                self.valid_source_versions.add((r.rule_id, 1))
            for g in GLOSSARY:
                self.valid_source_versions.add((g.term_id, 1))
            for f in FACTS:
                for v in f.versions:
                    self.valid_source_versions.add((f.fact_id, v.version))

    def verify_finding(
        self,
        finding: Finding,
        unit: Optional[ContentUnit] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Verify that a single finding satisfies all citation and evidence requirements.

        Returns:
            Tuple of (passes_verifier: bool, rejection_reason: Optional[str]).
        """
        # 1. Quote Veracity — quote must be non-empty
        if not finding.span.quote or not finding.span.quote.strip():
            return False, "Empty span quote."

        if unit:
            # Quote must exist verbatim in the ContentUnit text
            if finding.span.quote not in unit.text:
                return False, f"Quote '{finding.span.quote}' does not exist verbatim in ContentUnit."

            # Verify offsets align with the quote (within unit bounds)
            u_start = finding.span.start - unit.start
            u_end = finding.span.end - unit.start
            if 0 <= u_start < u_end <= len(unit.text):
                extracted_slice = unit.text[u_start:u_end]
                if extracted_slice != finding.span.quote:
                    return False, (
                        f"Offsets [{finding.span.start}:{finding.span.end}] do not align "
                        f"with quote '{finding.span.quote}'."
                    )

        # 2. Source Resolution — every evidence record must resolve
        if not finding.evidence:
            return False, "Finding lacks citation evidence."

        for ev in finding.evidence:
            if ev.source not in self.valid_source_ids:
                return False, (
                    f"Cited source '{ev.source}' does not resolve to an approved "
                    "knowledge base record."
                )
            if ev.version < 1:
                return False, f"Invalid source version '{ev.version}'."
            if self.valid_source_versions and (ev.source, ev.version) not in self.valid_source_versions:
                return False, (
                    f"Cited source version '{ev.source}@v{ev.version}' does not resolve "
                    "to a real knowledge base version."
                )

        # 3. Numeric Parsing & Comparison Recomputation — outdated/contradicted findings must cite a number
        if finding.type.value in ("outdated", "contradicted"):
            numbers_in_quote = re.findall(r"\d[\d,]*(?:\.\d+)?", finding.span.quote)
            if not numbers_in_quote:
                return False, (
                    f"Claim finding lacks parseable numerical figure in quote: "
                    f"'{finding.span.quote}'."
                )
            # Recompute comparison: if outdated finding claims quote is outdated,
            # but quote's number actually matches current active value, drop it.
            for ev in finding.evidence:
                if ev.status == "superseded" and ev.current_value:
                    curr_nums = re.findall(r"\d[\d,]*(?:\.\d+)?", ev.current_value)
                    if curr_nums and numbers_in_quote[0].replace(",", "") == curr_nums[0].replace(",", ""):
                        return False, "Recomputed comparison: quote already matches current active value."

        return True, None

    def filter_findings(
        self,
        findings: List[Finding],
        units_by_id: Optional[Dict[str, ContentUnit]] = None,
    ) -> Tuple[List[Finding], int, float]:
        """Filter out hallucinated or unverifiable findings.

        Returns:
            Tuple of (verified_findings, dropped_count, drop_rate).
        """
        verified: List[Finding] = []
        dropped_count = 0

        for f in findings:
            unit = units_by_id.get(f.span.unit_id) if units_by_id else None
            passes, reason = self.verify_finding(f, unit)
            if passes:
                verified.append(f)
            else:
                dropped_count += 1

        total = len(findings)
        drop_rate = (dropped_count / total) if total > 0 else 0.0
        return verified, dropped_count, drop_rate

    # ------------------------------------------------------------------
    # G2: Retrieval-trace enrichment for Unsupported findings
    # ------------------------------------------------------------------

    def enrich_unsupported_with_trace(
        self,
        findings: List[Finding],
        retrieval_traces: Optional[Dict[str, str]] = None,
    ) -> List[Finding]:
        """Embed the hybrid retrieval trace into Unsupported finding explanations (G2).

        For each Unsupported finding whose span quote has an entry in
        ``retrieval_traces``, the explanation is extended with the trace string
        showing which BM25 + vector candidates were searched.

        Args:
            findings: Findings list (post-verifier).
            retrieval_traces: Mapping of quote -> retrieval trace summary string.
                              Built by the retrieval node and passed through state.

        Returns:
            Findings with enriched explanations (Unsupported only).
        """
        if not retrieval_traces:
            return findings

        enriched: List[Finding] = []
        for f in findings:
            if f.type == FindingType.unsupported:
                trace = retrieval_traces.get(f.span.quote)
                if trace:
                    new_explanation = f.explanation.rstrip(".") + f". Retrieval trace: {trace}"
                    f = f.model_copy(update={
                        "explanation": new_explanation,
                        "disclosure": f.disclosure.model_copy(update={"method": Method.hybrid_retrieval}),
                    })
            enriched.append(f)
        return enriched

    def get_drop_rate(self, total_checked: int, dropped_count: int) -> float:
        """Compute verifier drop rate."""
        return (dropped_count / total_checked) if total_checked > 0 else 0.0
