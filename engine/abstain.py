"""Abstain / route_to rule for Axiom (PRD §4.3 A-12; R1 §2.5).

Implements:
- Abstain rule: findings that cannot be verified get `abstained=True` and
  status set to "Needs judgment" (displayed to reviewer, never asserted false).
- route_to assignment by finding type (R1 §2.5):
    * terminology  -> creator
    * outdated     -> legal_reviewer
    * contradicted -> legal_reviewer
    * unsupported  -> legal_reviewer
    * tone         -> creator
    * accessibility -> creator
    * visual       -> creator
    * <ambiguous>  -> reviewer  (rule kind=ambiguous, needs human judgment)
- Matched-source tracking: every source the run touched — including Supported
  claims — is recorded in `matched_sources` for impact analysis (PRD I3.4).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from contracts.models import Finding, FindingStatus, FindingType


# ---------------------------------------------------------------------------
# Route-to table (R1 §2.5)
# ---------------------------------------------------------------------------

ROUTE_TABLE: Dict[str, str] = {
    FindingType.terminology.value:  "creator",
    FindingType.tone.value:         "creator",
    FindingType.accessibility.value: "creator",
    FindingType.visual.value:       "creator",
    FindingType.outdated.value:     "legal_reviewer",
    FindingType.contradicted.value: "legal_reviewer",
    FindingType.unsupported.value:  "legal_reviewer",
}

DEFAULT_ROUTE = "reviewer"  # fallback for unknown types


def route_to_for_type(finding_type: str) -> str:
    """Return the correct role queue for a given finding type (R1 §2.5)."""
    return ROUTE_TABLE.get(finding_type, DEFAULT_ROUTE)


# ---------------------------------------------------------------------------
# Abstain rule
# ---------------------------------------------------------------------------

class AbstainRouter:
    """A-12: Abstain rule and route_to enforcement.

    For each finding the router:
    1. Ensures `route_to` matches R1 §2.5 (corrects if wrong).
    2. Marks ambiguous / unverifiable findings with `abstained=True`
       and `status=FindingStatus.disputed` (Needs judgment).
    3. Records every source matched by the run (including Supported hits)
       into `matched_sources` for the impact-analysis contract (PRD I3.4).
    """

    def process_findings(
        self,
        findings: List[Finding],
        additional_matched_sources: Optional[Set[str]] = None,
        ambiguous_rule_ids: Optional[Set[str]] = None,
    ) -> tuple[List[Finding], Set[str]]:
        """Apply abstain rule and route_to enforcement to all findings.

        Args:
            findings: Findings from upstream checkers / verifier.
            additional_matched_sources: Sources already recorded (e.g. Supported).
            ambiguous_rule_ids: Set of ambiguous rule IDs.

        Returns:
            Tuple of (processed_findings, all_matched_sources).
        """
        matched: Set[str] = set(additional_matched_sources or set())
        ambiguous = ambiguous_rule_ids or set()
        processed: List[Finding] = []

        for f in findings:
            # 1. Enforce correct route_to per R1 §2.5
            if f.rule_id and f.rule_id in ambiguous:
                correct_route = "reviewer"
            else:
                correct_route = route_to_for_type(f.type.value)

            # Allow overrides that are already correct to pass through unchanged
            updated = f.model_copy(update={"route_to": correct_route}) if f.route_to != correct_route else f

            # 2. Abstain: findings with abstained=True need human judgment
            if updated.abstained:
                updated = updated.model_copy(update={"status": FindingStatus.open})

            processed.append(updated)

            # 3. Record all sources this finding cites for impact analysis
            for ev in updated.evidence:
                matched.add(ev.source)
            if updated.rule_id:
                matched.add(updated.rule_id)

        return processed, matched

    def should_abstain(self, finding: Finding) -> bool:
        """Return True if this finding is ambiguous and should be flagged for human review.

        A finding should abstain if:
        - It is already marked abstained=True (upstream set this).
        - It has no evidence (cannot be verified).
        - Its confidence is below 0.5 (low-confidence judgment call).
        """
        if finding.abstained:
            return True
        if not finding.evidence:
            return True
        if finding.confidence < 0.5:
            return True
        return False

    def apply_needs_judgment(
        self,
        findings: List[Finding],
        ambiguous_rule_ids: Optional[Set[str]] = None,
    ) -> List[Finding]:
        """Tag findings that require human judgment with abstained=True.

        A finding requires judgment if:
        - It references an ambiguous brand rule (rule_id in ambiguous_rule_ids).
        - It falls below the confidence threshold.
        - It was already flagged abstained upstream.

        Args:
            findings: All findings after verification.
            ambiguous_rule_ids: Set of rule IDs with kind=ambiguous (from brand kit).

        Returns:
            Updated list with appropriate findings tagged for Needs judgment.
        """
        ambiguous = ambiguous_rule_ids or set()
        updated: List[Finding] = []
        for f in findings:
            if f.abstained:
                updated.append(f)
                continue
            needs_judgment = (
                (f.rule_id in ambiguous)
                or (f.confidence < 0.7)
            )
            if needs_judgment:
                new_expl = f.explanation
                if "Needs judgment" not in new_expl:
                    new_expl = f"Needs judgment: {new_expl}"
                updated.append(f.model_copy(update={"abstained": True, "explanation": new_expl}))
            else:
                updated.append(f)
        return updated


# ---------------------------------------------------------------------------
# Default instance and helpers
# ---------------------------------------------------------------------------

_DEFAULT_ROUTER = AbstainRouter()


def process_findings(
    findings: List[Finding],
    additional_matched_sources: Optional[Set[str]] = None,
) -> tuple[List[Finding], Set[str]]:
    """Apply abstain rule and route_to enforcement using the default router."""
    return _DEFAULT_ROUTER.process_findings(findings, additional_matched_sources)


def apply_needs_judgment(
    findings: List[Finding],
    ambiguous_rule_ids: Optional[Set[str]] = None,
) -> List[Finding]:
    """Tag ambiguous findings as Needs judgment using the default router."""
    return _DEFAULT_ROUTER.apply_needs_judgment(findings, ambiguous_rule_ids)

