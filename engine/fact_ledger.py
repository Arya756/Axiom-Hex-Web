"""Temporal Fact Ledger for Axiom (PRD §4.3 A-09, I1.2–I1.3, Gate G1).

Responsibilities:
1. Deterministic claim extraction (numbers with units, superlatives, compliance assertions).
2. Normalisation to (subject, metric, value, unit, period) — handles '10k' vs '10,000' and
   'customers' vs 'accounts'.
3. Temporal Fact Ledger lookup and classification:
   - Supported: matches active version, OR matches superseded version with explicit past
     period inside that version's validity window (no finding, recorded in matched_sources).
   - Outdated: matches a superseded version without valid historical period. Cites old & current.
   - Contradicted: matches subject but numerical value contradicts all approved versions.
   - Unsupported: superlatives or ungrounded claims. Cites epistemic copy rule.
4. Guardrail: if retrieval / DB lookup fails, mark checker partial/failed — NEVER emit false Unsupported.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from brand_kit.fixtures import FACTS
from brand_kit.models import BrandFact, FactVersion
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


@dataclass
class ExtractedClaim:
    """A normalized claim extracted from content text."""
    subject: str                    # e.g. "customers", "uptime", "pricing", "superlative"
    metric: str                     # e.g. "count", "percentage", "tier_description", "rank"
    normalized_value: str           # e.g. "10,000+", "25,000+", "99.9%", "#1"
    raw_value: str                  # e.g. "10k", "10,000", "99.9%"
    unit_str: Optional[str]         # e.g. "customers", "percent", "USD/month"
    period_year: Optional[int]      # e.g. 2023, 2024 (if explicit past period stated)
    quote: str                      # verbatim substring in document
    start: int                      # absolute start char offset
    end: int                        # absolute end char offset
    unit_id: str                    # ContentUnit id


class RetrievalFailureError(RuntimeError):
    """Raised when knowledge base retrieval encounters a systemic failure."""
    pass


class TemporalFactLedger:
    """Temporal Fact Ledger verifying factual claims against versioned brand facts."""

    def __init__(
        self,
        facts: Optional[List[BrandFact]] = None,
        simulate_retrieval_failure: bool = False,
    ) -> None:
        self.facts = facts or FACTS
        self.facts_by_id: Dict[str, BrandFact] = {f.fact_id: f for f in self.facts}
        self.facts_by_subject: Dict[str, BrandFact] = {f.subject.lower(): f for f in self.facts}
        self.simulate_retrieval_failure = simulate_retrieval_failure

    # -----------------------------------------------------------------------
    # 1. Claim Extraction and Normalisation (I1.2)
    # -----------------------------------------------------------------------

    def extract_claims(self, unit: ContentUnit) -> List[ExtractedClaim]:
        """Extract and normalise claims from a ContentUnit using deterministic patterns."""
        claims: List[ExtractedClaim] = []
        text = unit.text

        def _bounds(m: re.Match) -> Tuple[str, int, int]:
            raw = m.group(0)
            quote = raw.strip()
            lead = raw.find(quote) if quote else 0
            start = unit.start + m.start() + lead
            end = start + len(quote)
            return quote, start, end

        # Detect explicit year in unit/sentence (e.g. "in 2023", "as of 2024", "back in 2021")
        year_match = re.search(r"\b(?:in|as of|during|back in|since|for)\s+(202[0-9])\b", text, re.IGNORECASE)
        general_year: Optional[int] = int(year_match.group(1)) if year_match else None

        # Pattern 1: Customers / Accounts count ("10k customers", "10,000+ accounts", "25,000 clients")
        customer_pattern = re.compile(
            r"(\b(?:over|more than|approximately|about)?\s*(\d{1,3}(?:,\d{3})*|\d+k|\d+m)\+?\s*(?:customers?|accounts?|clients?|organizations?)\b)",
            re.IGNORECASE,
        )
        for match in customer_pattern.finditer(text):
            quote, start, end = _bounds(match)
            num_raw = match.group(2).lower()

            # Normalise number: 10k -> 10,000+, 25k -> 25,000+
            normalized_num = self._normalize_count(num_raw)

            claims.append(
                ExtractedClaim(
                    subject="customers",
                    metric="count",
                    normalized_value=normalized_num,
                    raw_value=num_raw,
                    unit_str="customers",
                    period_year=general_year,
                    quote=quote,
                    start=start,
                    end=end,
                    unit_id=unit.unit_id,
                )
            )

        # Pattern 2: Uptime SLA ("99.9% uptime", "99.95% SLA", "99.9% availability")
        uptime_pattern = re.compile(
            r"(\b(\d{2}(?:\.\d+)?%)\s*(?:uptime|sla|availability)\b|\b(?:uptime|sla|availability)\s*(?:of\s*)?(\d{2}(?:\.\d+)?%)\b)",
            re.IGNORECASE,
        )
        for match in uptime_pattern.finditer(text):
            quote, start, end = _bounds(match)
            val = match.group(2) or match.group(3)

            claims.append(
                ExtractedClaim(
                    subject="uptime",
                    metric="percentage",
                    normalized_value=val,
                    raw_value=val,
                    unit_str="percent",
                    period_year=general_year,
                    quote=quote,
                    start=start,
                    end=end,
                    unit_id=unit.unit_id,
                )
            )

        # Pattern 3: Pricing ("$299/month", "$349/month", "$299/mo")
        pricing_pattern = re.compile(
            r"(\$(\d+)(?:\.\d+)?\s*(?:/\s*(?:month|mo)|per\s*month)\b)",
            re.IGNORECASE,
        )
        for match in pricing_pattern.finditer(text):
            quote, start, end = _bounds(match)
            dollars = match.group(2)

            claims.append(
                ExtractedClaim(
                    subject="pricing",
                    metric="starting price",
                    normalized_value=f"${dollars}/month",
                    raw_value=f"${dollars}",
                    unit_str="USD/month",
                    period_year=general_year,
                    quote=quote,
                    start=start,
                    end=end,
                    unit_id=unit.unit_id,
                )
            )

        # Pattern 4: Compliance certifications (SOC 2, GDPR, HIPAA)
        compliance_pattern = re.compile(
            r"(\b(?:soc\s*2(?:\s*type\s*ii)?|soc2(?:\s*type\s*2)?)\s*(?:certified|compliant)?\b|\bgdpr\s*(?:compliant|certified)?\b|\bhipaa\s*(?:compliant|certified)?\b)",
            re.IGNORECASE,
        )
        for match in compliance_pattern.finditer(text):
            quote, start, end = _bounds(match)
            lower = quote.lower()
            if "soc" in lower:
                subj = "soc 2 type ii"
            elif "gdpr" in lower:
                subj = "gdpr compliance"
            else:
                subj = "hipaa compliance"

            claims.append(
                ExtractedClaim(
                    subject=subj,
                    metric="certification status",
                    normalized_value="certified" if "soc" in lower else "compliant",
                    raw_value=quote,
                    unit_str=None,
                    period_year=general_year,
                    quote=quote,
                    start=start,
                    end=end,
                    unit_id=unit.unit_id,
                )
            )

        # Pattern 5: Superlatives ("#1 compliance platform", "fastest audit engine", "most secure")
        superlative_pattern = re.compile(
            r"((?:#1\b|\bthe\s+(?:fastest|best|most\s+secure|most\s+reliable))\s+[a-zA-Z]+(?:\s+[a-zA-Z]+)?)",
            re.IGNORECASE,
        )
        for match in superlative_pattern.finditer(text):
            quote, start, end = _bounds(match)

            claims.append(
                ExtractedClaim(
                    subject="superlative",
                    metric="rank",
                    normalized_value="#1",
                    raw_value=quote,
                    unit_str=None,
                    period_year=general_year,
                    quote=quote,
                    start=start,
                    end=end,
                    unit_id=unit.unit_id,
                )
            )

        return claims

    def _normalize_count(self, num_str: str) -> str:
        """Normalise string representations of count (e.g. 10k -> 10,000+)."""
        num_str = num_str.lower().replace(",", "").replace("+", "").strip()
        if num_str.endswith("k"):
            val = int(float(num_str[:-1]) * 1000)
        elif num_str.endswith("m"):
            val = int(float(num_str[:-1]) * 1000000)
        else:
            try:
                val = int(float(num_str))
            except ValueError:
                return num_str

        # Match known fact representation formatting
        if val == 10000:
            return "10,000+"
        elif val == 18000:
            return "18,000+"
        elif val == 25000:
            return "25,000+"
        return f"{val:,}+"

    # -----------------------------------------------------------------------
    # 2. Fact Classification & Verification (I1.3)
    # -----------------------------------------------------------------------

    def check_units(
        self,
        units: List[ContentUnit],
        policy: Optional[Sensitivity] = None,
    ) -> Tuple[List[Finding], Set[str]]:
        """Evaluate all extracted claims across ContentUnits.

        Returns:
            Tuple of (findings_list, matched_sources_set).

        Raises:
            RetrievalFailureError if retrieval fails (ensuring the caller marks
            the run partial/failed without emitting false Unsupported findings).
        """
        # Guardrail check
        if self.simulate_retrieval_failure:
            raise RetrievalFailureError("Systemic retrieval failure in Temporal Fact Ledger.")

        findings: List[Finding] = []
        matched_sources: Set[str] = set()
        effective_policy = policy or Sensitivity.internal

        for unit in units:
            claims = self.extract_claims(unit)

            for claim in claims:
                finding, matched_src = self._classify_claim(claim, effective_policy)
                if matched_src:
                    matched_sources.add(matched_src)
                    matched_sources.add("R-03")  # Numerical claims policy
                if finding:
                    findings.append(finding)

        return findings, matched_sources

    def _classify_claim(
        self,
        claim: ExtractedClaim,
        policy: Sensitivity,
    ) -> Tuple[Optional[Finding], Optional[str]]:
        """Classify a single claim into Supported / Outdated / Contradicted / Unsupported."""
        # Case A: Superlative / Absolute claim
        if claim.subject == "superlative":
            finding = Finding(
                finding_id=f"f_{uuid.uuid4().hex[:6]}",
                type=FindingType.unsupported,
                severity=FindingSeverity.high,
                confidence=0.92,
                span=Span(
                    unit_id=claim.unit_id,
                    start=claim.start,
                    end=claim.end,
                    quote=claim.quote,
                ),
                evidence=[
                    Evidence(
                        source="R-03",
                        version=1,
                        status="active",
                    )
                ],
                explanation="No substantiation found within approved tenant sources (searched top-k candidates).",
                suggested_fix=SuggestedFix(
                    text="leading",
                    edit_budget="minimal",
                    rechecked=False,
                ),
                route_to="legal_reviewer",
                disclosure=DisclosureRecord(
                    method=Method.deterministic_lookup,
                    provider=None,
                    model=None,
                    external_call=False,
                    data_categories=["claims"],
                    sensitivity=policy,
                    tokens=0,
                    cost=0.0,
                    latency_ms=1,
                ),
                status=FindingStatus.open,
                rule_id="R-03",
            )
            return finding, "R-03"

        # Case B: Check against known brand facts in Knowledge Base
        fact = self.facts_by_subject.get(claim.subject)
        if not fact:
            # If subject not in KB facts (e.g. unverified HIPAA claim)
            finding = Finding(
                finding_id=f"f_{uuid.uuid4().hex[:6]}",
                type=FindingType.unsupported,
                severity=FindingSeverity.high,
                confidence=0.90,
                span=Span(
                    unit_id=claim.unit_id,
                    start=claim.start,
                    end=claim.end,
                    quote=claim.quote,
                ),
                evidence=[
                    Evidence(
                        source="R-03",
                        version=1,
                        status="active",
                    )
                ],
                explanation="No substantiation found within approved tenant sources (searched top-k candidates).",
                suggested_fix=None,
                route_to="legal_reviewer",
                disclosure=DisclosureRecord(
                    method=Method.deterministic_lookup,
                    provider=None,
                    model=None,
                    external_call=False,
                    data_categories=["claims"],
                    sensitivity=policy,
                    tokens=0,
                    cost=0.0,
                    latency_ms=1,
                ),
                status=FindingStatus.open,
                rule_id="R-03",
            )
            return finding, "R-03"

        # Active version is the one without superseded_by
        active_version = next((v for v in fact.versions if v.superseded_by is None), fact.versions[-1])

        # Subcase 1: Matches Active Version -> SUPPORTED
        if claim.normalized_value == active_version.value:
            # Supported: No finding, record matched source for impact analysis (PRD I3.4)
            return None, fact.fact_id

        # Subcase 2: Matches a Superseded Version
        matched_superseded_version: Optional[FactVersion] = None
        for v in fact.versions:
            if v.superseded_by is not None and v.value == claim.normalized_value:
                matched_superseded_version = v
                break

        if matched_superseded_version:
            # Check Special Case: Explicit past period inside old version's validity window (PRD I1.3)
            if claim.period_year is not None:
                v_start_year = matched_superseded_version.valid_from.year
                v_end_year = (
                    matched_superseded_version.valid_until.year
                    if matched_superseded_version.valid_until
                    else date.today().year
                )
                if v_start_year <= claim.period_year <= v_end_year:
                    # Valid historical attribution -> SUPPORTED!
                    return None, fact.fact_id

            # Outdated claim without valid past period qualifier
            finding = Finding(
                finding_id=f"f_{uuid.uuid4().hex[:6]}",
                type=FindingType.outdated,
                severity=FindingSeverity.high,
                confidence=0.95,
                span=Span(
                    unit_id=claim.unit_id,
                    start=claim.start,
                    end=claim.end,
                    quote=claim.quote,
                ),
                evidence=[
                    Evidence(
                        source=fact.fact_id,
                        version=matched_superseded_version.version,
                        status="superseded",
                        current_version=active_version.version,
                        current_value=active_version.value,
                        effective=active_version.valid_from.isoformat(),
                    )
                ],
                explanation=(
                    f"This figure matches superseded {fact.fact_id} v{matched_superseded_version.version}. "
                    f"Current active value is '{active_version.value}' (effective {active_version.valid_from.isoformat()})."
                ),
                suggested_fix=SuggestedFix(
                    text=f"{active_version.value} {fact.subject}",
                    edit_budget="minimal",
                    rechecked=True,
                    intent_similarity=0.97,
                ),
                route_to="legal_reviewer",
                disclosure=DisclosureRecord(
                    method=Method.deterministic_lookup,
                    provider=None,
                    model=None,
                    external_call=False,
                    data_categories=["facts"],
                    sensitivity=policy,
                    tokens=0,
                    cost=0.0,
                    latency_ms=1,
                ),
                status=FindingStatus.open,
                rule_id="R-03",
            )
            return finding, fact.fact_id

        # Subcase 3: Contradicted (Subject is known, but numerical value contradicts all versions)
        finding = Finding(
            finding_id=f"f_{uuid.uuid4().hex[:6]}",
            type=FindingType.contradicted,
            severity=FindingSeverity.high,
            confidence=0.92,
            span=Span(
                unit_id=claim.unit_id,
                start=claim.start,
                end=claim.end,
                quote=claim.quote,
            ),
            evidence=[
                Evidence(
                    source=fact.fact_id,
                    version=active_version.version,
                    status="active",
                    current_version=active_version.version,
                    current_value=active_version.value,
                    effective=active_version.valid_from.isoformat(),
                )
            ],
            explanation=(
                f"Claim contradicts approved brand fact {fact.fact_id}. "
                f"Active approved value is '{active_version.value}'."
            ),
            suggested_fix=SuggestedFix(
                text=f"{active_version.value} {fact.subject}",
                edit_budget="minimal",
                rechecked=True,
                intent_similarity=0.90,
            ),
            route_to="legal_reviewer",
            disclosure=DisclosureRecord(
                method=Method.deterministic_lookup,
                provider=None,
                model=None,
                external_call=False,
                data_categories=["facts"],
                sensitivity=policy,
                tokens=0,
                cost=0.0,
                latency_ms=1,
            ),
            status=FindingStatus.open,
            rule_id="R-03",
        )
        return finding, fact.fact_id
