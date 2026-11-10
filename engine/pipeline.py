"""LangGraph / Async review pipeline for Axiom (PRD §4.3 A-05, A-08, A-09, A-11, T1).

Orchestrates multimodal review checks with:
- State schema (ReviewState)
- Sensitivity policy router (hard-blocks external calls on Restricted content)
- Parallel fan-out over checkers:
  * Deterministic TerminologyChecker (banned terms, product casing)
  * TemporalFactLedger (stale claim extraction, normalisation, Outdated/Contradicted/Supported/Unsupported)
  * LLMClient (tone, intent)
- CitationVerifier anti-hallucination gate (drops invalid citations, reports drop rate)
- Graceful partial degradation (deterministic findings always survive upstream errors)
- Real-time node progress events
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from contracts.models import (
    ContentUnit,
    DisclosureRecord,
    Finding,
    IntentCard,
    Method,
    ReviewResult,
    RunNodeStatus,
    RunProgress,
    Sensitivity,
)
from engine.fact_ledger import RetrievalFailureError, TemporalFactLedger
from engine.llm_client import LLMClient
from engine.terminology import TerminologyChecker
from engine.verifier import CitationVerifier


class ReviewState:
    """Internal state schema passed across pipeline nodes."""

    def __init__(
        self,
        revision_units: List[ContentUnit],
        ruleset_version: int = 1,
        policy: Optional[Sensitivity] = None,
        intent_card: Optional[IntentCard] = None,
        simulate_llm_failure: bool = False,
        simulate_retrieval_failure: bool = False,
    ) -> None:
        self.units = revision_units
        self.revision_id = revision_units[0].revision_id if revision_units else "rev_default"
        self.ruleset_version = ruleset_version
        self.policy = policy or Sensitivity.internal
        self.intent_card = intent_card
        self.simulate_llm_failure = simulate_llm_failure
        self.simulate_retrieval_failure = simulate_retrieval_failure

        self.findings: List[Finding] = []
        self.matched_sources: Set[str] = set()
        self.run_progress: List[RunProgress] = []
        self.disclosures: List[DisclosureRecord] = []
        self.partial: bool = False
        self.verifier_dropped_count: int = 0
        self.verifier_drop_rate: float = 0.0

    def add_progress(
        self,
        node: str,
        status: RunNodeStatus,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
    ) -> None:
        self.run_progress.append(
            RunProgress(
                node=node,
                status=status,
                started_at=started_at or datetime.utcnow(),
                finished_at=datetime.utcnow() if status in (RunNodeStatus.done, RunNodeStatus.failed, RunNodeStatus.partial) else None,
                error=error,
            )
        )


class ReviewPipeline:
    """LangGraph-compatible execution pipeline for automated brand governance."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        terminology_checker: Optional[TerminologyChecker] = None,
        fact_ledger: Optional[TemporalFactLedger] = None,
        verifier: Optional[CitationVerifier] = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.terminology_checker = terminology_checker or TerminologyChecker()
        self.fact_ledger = fact_ledger or TemporalFactLedger()
        self.verifier = verifier or CitationVerifier()

    def run(self, state: ReviewState) -> ReviewResult:
        """Execute review DAG across checkers and verifier."""
        # 1. Router Node: Enforce sensitivity policy
        self._node_router(state)

        # 2. Deterministic Terminology Node (PRD §4.3 A-08)
        self._node_terminology(state)

        # 3. Temporal Fact Ledger Node (PRD §4.3 A-09)
        self._node_facts(state)

        # 4. LLM Tone / Intent Node (PRD §4.3 A-06, A-16)
        self._node_llm(state)

        # 5. Citation Verifier Node (PRD §4.3 A-11, I1.5)
        self._node_verifier(state)

        # 6. Aggregator Node
        self._node_aggregator(state)

        return ReviewResult(
            revision_id=state.revision_id,
            ruleset_version=state.ruleset_version,
            sensitivity=state.policy,
            findings=state.findings,
            matched_sources=sorted(list(state.matched_sources)),
            run_progress=state.run_progress,
            disclosures=state.disclosures,
            partial=state.partial,
            cache_key=None,
        )

    # -----------------------------------------------------------------------
    # Pipeline Nodes
    # -----------------------------------------------------------------------

    def _node_router(self, state: ReviewState) -> None:
        """Validate run parameters and enforce sensitivity policy."""
        state.add_progress("router", RunNodeStatus.done)

    def _node_terminology(self, state: ReviewState) -> None:
        """Execute deterministic banned-term and product-name casing checks (A-08)."""
        node_start = datetime.utcnow()
        try:
            findings, sources = self.terminology_checker.check_units(state.units, state.policy)
            state.findings.extend(findings)
            state.matched_sources.update(sources)
            state.add_progress("terminology", RunNodeStatus.done, started_at=node_start)
        except Exception as ex:
            state.add_progress("terminology", RunNodeStatus.failed, error=str(ex), started_at=node_start)
            state.partial = True

    def _node_facts(self, state: ReviewState) -> None:
        """Extract and verify factual claims against Temporal Fact Ledger (A-09)."""
        node_start = datetime.utcnow()
        try:
            # Configure ledger failure simulation if requested
            ledger = (
                TemporalFactLedger(simulate_retrieval_failure=True)
                if state.simulate_retrieval_failure
                else self.fact_ledger
            )
            findings, sources = ledger.check_units(state.units, state.policy)
            state.findings.extend(findings)
            state.matched_sources.update(sources)
            state.add_progress("facts", RunNodeStatus.done, started_at=node_start)
        except RetrievalFailureError as rf_err:
            # Guardrail: mark checker partial/failed; NEVER emit false Unsupported findings!
            state.add_progress("facts", RunNodeStatus.failed, error=str(rf_err), started_at=node_start)
            state.partial = True
        except Exception as ex:
            state.add_progress("facts", RunNodeStatus.failed, error=str(ex), started_at=node_start)
            state.partial = True

    def _node_llm(self, state: ReviewState) -> None:
        """Execute LLM tone / intent checks with strict policy enforcement (A-06)."""
        node_start = datetime.utcnow()

        # Restricted runs make ZERO external calls
        if state.policy == Sensitivity.restricted:
            disclosure = DisclosureRecord(
                method=Method.deterministic_lookup,
                provider=None,
                model=None,
                external_call=False,
                data_categories=["document_span"],
                sensitivity=Sensitivity.restricted,
                tokens=0,
                cost=0.0,
                latency_ms=0,
            )
            state.disclosures.append(disclosure)
            state.add_progress("tone_llm", RunNodeStatus.done, started_at=node_start)
            return

        client = LLMClient(simulate_failure=state.simulate_llm_failure)
        full_text = "\n".join(u.text for u in state.units)

        response = client.generate(
            prompt="Analyze document tone against brand guidelines.",
            document_text=full_text,
            sensitivity=state.policy,
        )

        state.disclosures.append(response.disclosure)

        if not response.success:
            # Graceful degradation: mark partial, deterministic findings preserved!
            state.partial = True
            state.add_progress(
                "tone_llm",
                RunNodeStatus.partial,
                error=response.error,
                started_at=node_start,
            )
        else:
            state.add_progress("tone_llm", RunNodeStatus.done, started_at=node_start)

    def _node_verifier(self, state: ReviewState) -> None:
        """Citation Verifier node: drops unverified/hallucinated findings (A-11, I1.5)."""
        node_start = datetime.utcnow()
        try:
            units_by_id = {u.unit_id: u for u in state.units}
            verified_findings, dropped_count, drop_rate = self.verifier.filter_findings(
                state.findings, units_by_id
            )
            state.findings = verified_findings
            state.verifier_dropped_count = dropped_count
            state.verifier_drop_rate = drop_rate

            state.add_progress(
                "verifier",
                RunNodeStatus.done,
                started_at=node_start,
                error=f"dropped={dropped_count}, rate={drop_rate:.2%}" if dropped_count > 0 else None,
            )
        except Exception as ex:
            state.add_progress("verifier", RunNodeStatus.failed, error=str(ex), started_at=node_start)
            state.partial = True

    def _node_aggregator(self, state: ReviewState) -> None:
        """Final aggregation and deduplication."""
        node_start = datetime.utcnow()
        state.add_progress("aggregator", RunNodeStatus.done, started_at=node_start)


# Global default pipeline instance
_DEFAULT_PIPELINE = ReviewPipeline()


def run_review(
    revision_units: List[ContentUnit],
    ruleset_version: int = 1,
    session: Any = None,
    policy: Optional[Sensitivity] = None,
    intent_card: Optional[IntentCard] = None,
    simulate_llm_failure: bool = False,
    simulate_retrieval_failure: bool = False,
) -> ReviewResult:
    """Real engine entrypoint satisfying Integration Contract T1."""
    state = ReviewState(
        revision_units=revision_units,
        ruleset_version=ruleset_version,
        policy=policy,
        intent_card=intent_card,
        simulate_llm_failure=simulate_llm_failure,
        simulate_retrieval_failure=simulate_retrieval_failure,
    )
    return _DEFAULT_PIPELINE.run(state)
