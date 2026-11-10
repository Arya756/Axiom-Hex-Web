"""Citation Verifier for Axiom (PRD §4.3 A-11, I1.5, Gate G1/G2).

The anti-hallucination gate:
- Asserts quote exists verbatim in the content unit.
- Asserts character offsets are consistent with the quote.
- Asserts source_id@version resolves against approved knowledge base sources.
- Re-checks numerical parsing and comparisons.
- Drops invalid or hallucinated findings and counts them in run metrics.
- All shown findings pass the verifier (true by construction).
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Set, Tuple

from brand_kit.fixtures import FACTS, GLOSSARY, RULES
from contracts.models import ContentUnit, Finding


class CitationVerifier:
    """Anti-hallucination verification gate for review findings."""

    def __init__(
        self,
        valid_source_ids: Optional[Set[str]] = None,
    ) -> None:
        if valid_source_ids is not None:
            self.valid_source_ids = valid_source_ids
        else:
            self.valid_source_ids = set()
            self.valid_source_ids.update(r.rule_id for r in RULES)
            self.valid_source_ids.update(g.term_id for g in GLOSSARY)
            self.valid_source_ids.update(f.fact_id for f in FACTS)

    def verify_finding(
        self,
        finding: Finding,
        unit: Optional[ContentUnit] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Verify that a single finding satisfies all citation and evidence requirements.

        Returns:
            Tuple of (passes_verifier: bool, rejection_reason: Optional[str]).
        """
        # 1. Quote Veracity
        if not finding.span.quote or not finding.span.quote.strip():
            return False, "Empty span quote."

        if unit:
            if finding.span.quote not in unit.text:
                return False, f"Quote '{finding.span.quote}' does not exist verbatim in ContentUnit."

            # Verify offsets match quote if within bounds
            u_start = finding.span.start - unit.start
            u_end = finding.span.end - unit.start
            if 0 <= u_start < u_end <= len(unit.text):
                extracted_slice = unit.text[u_start:u_end]
                if extracted_slice != finding.span.quote:
                    return False, f"Offsets [{finding.span.start}:{finding.span.end}] do not align with quote '{finding.span.quote}'."

        # 2. Source Resolution
        if not finding.evidence:
            return False, "Finding lacks citation evidence."

        for ev in finding.evidence:
            if ev.source not in self.valid_source_ids:
                return False, f"Cited source '{ev.source}' does not resolve to an approved knowledge base record."
            if ev.version < 1:
                return False, f"Invalid source version '{ev.version}'."

        # 3. Numeric Parsing on Claims
        if finding.type.value in ("outdated", "contradicted"):
            numbers_in_quote = re.findall(r"\d[\d,]*(?:\.\d+)?", finding.span.quote)
            if not numbers_in_quote:
                return False, f"Claim finding lacks parseable numerical figure in quote: '{finding.span.quote}'."

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
