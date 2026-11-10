"""Deterministic Terminology Checker for Axiom (PRD §4.3 A-08, G1).

Performs regex-based detection of banned terms and product-name casing rules
without invoking external LLMs.

Rules enforced:
- Banned terms from brand kit glossary (e.g. 'MFP', 'MF', 'the platform', 'brand policing')
- Product-name proper casing (e.g. 'meridian flow' -> 'Meridian Flow')
- Platform terminology proper casing (e.g. 'knowledge base' -> 'Knowledge Base',
  'intent card' -> 'Intent Card', 'temporal fact ledger' -> 'Temporal Fact Ledger',
  'citation verifier' -> 'Citation Verifier', 'ambiguity radar' -> 'Ambiguity Radar')
"""

from __future__ import annotations

import re
import uuid
from typing import Dict, List, Optional, Set, Tuple

from brand_kit.fixtures import GLOSSARY
from brand_kit.models import GlossaryTerm
from contracts.models import (
    ContentUnit,
    DisclosureRecord,
    Evidence,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingType,
    Method,
    Sensitivity,
    Span,
    SuggestedFix,
)


class TerminologyChecker:
    """Deterministic, regex-driven terminology and casing enforcement engine."""

    def __init__(self, glossary: Optional[List[GlossaryTerm]] = None) -> None:
        self.glossary = glossary or GLOSSARY
        self.term_map: Dict[str, GlossaryTerm] = {t.term_id: t for t in self.glossary}

        # Case-sensitive canonical platform terms that require specific title/capital casing
        self.canonical_cased_terms: List[Tuple[str, str, str]] = [
            # (canonical_cased, pattern_lower, term_id)
            ("Meridian Flow", r"\bmeridian\s+flow\b", "G-01"),
            ("Meridian Flow Platform", r"\bmeridian\s+flow\s+platform\b", "G-02"),
            ("Knowledge Base", r"\bknowledge\s+base\b", "G-07"),
            ("Intent Card", r"\bintent\s+card\b", "G-08"),
            ("Temporal Fact Ledger", r"\btemporal\s+fact\s+ledger\b", "G-12"),
            ("Citation Verifier", r"\bcitation\s+verifier\b", "G-13"),
            ("Ambiguity Radar", r"\bambiguity\s+radar\b", "G-14"),
        ]

    def check_units(
        self,
        units: List[ContentUnit],
        policy: Optional[Sensitivity] = None,
    ) -> Tuple[List[Finding], Set[str]]:
        """Run terminology and casing checks across ContentUnits.

        Returns:
            Tuple of (findings_list, matched_sources_set).
        """
        findings: List[Finding] = []
        matched_sources: Set[str] = set()
        effective_policy = policy or Sensitivity.internal

        for unit in units:
            unit_text = unit.text
            occupied_spans: List[Tuple[int, int]] = []

            def _is_overlapping(s: int, e: int) -> bool:
                return any(max(s, o_s) < min(e, o_e) for o_s, o_e in occupied_spans)

            # 1. Product and Platform Term Casing Check
            for canonical, regex_pattern, term_id in self.canonical_cased_terms:
                for match in re.finditer(regex_pattern, unit_text, re.IGNORECASE):
                    quote = match.group(0)
                    start = unit.start + match.start()
                    end = unit.start + match.end()

                    # Only flag if casing differs from canonical preferred casing
                    if quote != canonical and not _is_overlapping(start, end):
                        occupied_spans.append((start, end))
                        matched_sources.add(term_id)
                        matched_sources.add("R-01")

                        finding = Finding(
                            finding_id=f"f_{uuid.uuid4().hex[:6]}",
                            type=FindingType.terminology,
                            severity=FindingSeverity.medium,
                            confidence=1.0,
                            span=Span(
                                unit_id=unit.unit_id,
                                start=start,
                                end=end,
                                quote=quote,
                            ),
                            evidence=[
                                Evidence(
                                    source=term_id,
                                    version=1,
                                    status="active",
                                    current_version=1,
                                    current_value=canonical,
                                )
                            ],
                            explanation=f"Improper casing '{quote}' detected. Use official capitalization '{canonical}'.",
                            suggested_fix=SuggestedFix(
                                text=canonical,
                                edit_budget="minimal",
                                rechecked=True,
                                intent_similarity=1.0,
                            ),
                            route_to="creator",
                            disclosure=DisclosureRecord(
                                method=Method.deterministic_lookup,
                                provider=None,
                                model=None,
                                external_call=False,
                                data_categories=["terminology"],
                                sensitivity=effective_policy,
                                tokens=0,
                                cost=0.0,
                                latency_ms=1,
                            ),
                            status=FindingStatus.open,
                            rule_id="R-01",
                        )
                        findings.append(finding)

            # 2. Banned Terms Check
            for term in self.glossary:
                for banned in term.banned:
                    # Case-insensitive word boundary match
                    pattern = re.compile(rf"\b{re.escape(banned)}\b", re.IGNORECASE)
                    for match in pattern.finditer(unit_text):
                        quote = match.group(0)
                        start = unit.start + match.start()
                        end = unit.start + match.end()

                        # Skip if already canonical preferred term or overlapping span
                        if quote == term.preferred or _is_overlapping(start, end):
                            continue

                        occupied_spans.append((start, end))
                        matched_sources.add(term.term_id)
                        matched_sources.add("R-01")

                        finding = Finding(
                            finding_id=f"f_{uuid.uuid4().hex[:6]}",
                            type=FindingType.terminology,
                            severity=FindingSeverity.medium,
                            confidence=1.0,
                            span=Span(
                                unit_id=unit.unit_id,
                                start=start,
                                end=end,
                                quote=quote,
                            ),
                            evidence=[
                                Evidence(
                                    source=term.term_id,
                                    version=1,
                                    status="active",
                                    current_version=1,
                                    current_value=term.preferred,
                                )
                            ],
                            explanation=f"Banned term '{quote}' detected. Use preferred term '{term.preferred}'.",
                            suggested_fix=SuggestedFix(
                                text=term.preferred,
                                edit_budget="minimal",
                                rechecked=True,
                                intent_similarity=1.0,
                            ),
                            route_to="creator",
                            disclosure=DisclosureRecord(
                                method=Method.deterministic_lookup,
                                provider=None,
                                model=None,
                                external_call=False,
                                data_categories=["terminology"],
                                sensitivity=effective_policy,
                                tokens=0,
                                cost=0.0,
                                latency_ms=1,
                            ),
                            status=FindingStatus.open,
                            rule_id="R-01",
                        )
                        findings.append(finding)

        return findings, matched_sources
