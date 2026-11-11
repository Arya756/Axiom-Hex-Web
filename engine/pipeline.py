"""LangGraph / Async review pipeline for Axiom (PRD §4.3 A-05, A-08..A-12, T1).

Orchestrates multimodal review checks with:
- State schema (ReviewState)
- Sensitivity policy router (hard-blocks external calls on Restricted content)
- Parallel fan-out over checkers:
  * Deterministic TerminologyChecker (banned terms, product casing)        — A-08
  * TemporalFactLedger (stale claim extraction, normalisation, classify)   — A-09
  * HybridRetriever (BM25 + vector KNN + RRF, tenant-scoped, trace)       — A-10
  * LLMClient (tone, intent, XML-sandboxed)                                — A-06
- CitationVerifier anti-hallucination gate + trace enrichment              — A-11
- AbstainRouter: route_to enforcement + Needs judgment tagging             — A-12
- Graceful partial degradation (deterministic findings always survive)
- Real-time node progress events (T6)
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
from engine.abstain import AbstainRouter
from engine.accessibility import AccessibilityVisualChecker
from engine.fact_ledger import RetrievalFailureError, TemporalFactLedger
from engine.intent_card import extract_intent_card, generate_minimal_fix
from engine.llm_client import LLMClient
from engine.retrieval import HybridRetriever, get_default_retriever
from engine.terminology import TerminologyChecker
from engine.tone import ToneChecker
from engine.verifier import CitationVerifier


class ReviewState:
    """Internal state schema passed across pipeline nodes."""

    def __init__(
        self,
        revision_units: List[ContentUnit],
        ruleset_version: int = 1,
        policy: Optional[Sensitivity] = None,
        intent_card: Optional[IntentCard] = None,
        session: Any = None,
        tenant_id: str = "tenant_meridian",
        simulate_llm_failure: bool = False,
        simulate_retrieval_failure: bool = False,
    ) -> None:
        self.units = revision_units
        self.revision_id = revision_units[0].revision_id if revision_units else "rev_default"
        self.ruleset_version = ruleset_version
        self.policy = policy or Sensitivity.internal
        self.intent_card = intent_card
        self.session = session
        self.tenant_id = tenant_id
        self.simulate_llm_failure = simulate_llm_failure
        self.simulate_retrieval_failure = simulate_retrieval_failure

        self.findings: List[Finding] = []
        self.matched_sources: Set[str] = set()
        self.run_progress: List[RunProgress] = []
        self.disclosures: List[DisclosureRecord] = []
        self.partial: bool = False

        # Verifier metrics
        self.verifier_dropped_count: int = 0
        self.verifier_drop_rate: float = 0.0

        # Retrieval traces — quote -> trace summary string (for Unsupported receipts)
        self.retrieval_traces: Dict[str, str] = {}

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
                finished_at=datetime.utcnow() if status in (
                    RunNodeStatus.done, RunNodeStatus.failed, RunNodeStatus.partial
                ) else None,
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
        retriever: Optional[HybridRetriever] = None,
        accessibility_checker: Optional[AccessibilityVisualChecker] = None,
        tone_checker: Optional[ToneChecker] = None,
        verifier: Optional[CitationVerifier] = None,
        abstain_router: Optional[AbstainRouter] = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.terminology_checker = terminology_checker or TerminologyChecker()
        self.fact_ledger = fact_ledger or TemporalFactLedger()
        self.retriever = retriever  # None = lazy-loaded from default
        self.accessibility_checker = accessibility_checker or AccessibilityVisualChecker()
        self.tone_checker = tone_checker or ToneChecker()
        self.verifier = verifier or CitationVerifier()
        self.abstain_router = abstain_router or AbstainRouter()

    def _get_retriever(self) -> HybridRetriever:
        if self.retriever is not None:
            return self.retriever
        return get_default_retriever()

    def run(self, state: ReviewState) -> ReviewResult:
        """Execute review DAG across checkers and verifier."""
        # 1. Router — enforce sensitivity policy
        self._node_router(state)

        # 2. Terminology checker (A-08)
        self._node_terminology(state)

        # 3. Temporal Fact Ledger (A-09)
        self._node_facts(state)

        # 4. Hybrid Retrieval (A-10) — enrich Unsupported findings with traces
        self._node_retrieval(state)

        # 5. Accessibility & Visual checks (A-14, A-15, I2.1..I2.6)
        self._node_accessibility_visual(state)

        # 6. LLM Tone / Intent (A-06)
        self._node_llm(state)

        # 6. Citation Verifier (A-11)
        self._node_verifier(state)

        # 7. Abstain / route_to (A-12)
        self._node_abstain(state)

        # 8. Aggregator
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
        """Validate run parameters, enforce sensitivity policy, and auto-extract Intent Card (A-13)."""
        node_start = datetime.utcnow()
        if state.intent_card is None:
            state.intent_card = extract_intent_card(state.units)
        state.add_progress("router", RunNodeStatus.done, started_at=node_start)

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
        """Extract and verify factual claims via Temporal Fact Ledger (A-09)."""
        node_start = datetime.utcnow()
        try:
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
            # Guardrail: mark partial/failed; NEVER emit false Unsupported findings!
            state.add_progress("facts", RunNodeStatus.failed, error=str(rf_err), started_at=node_start)
            state.partial = True
        except Exception as ex:
            state.add_progress("facts", RunNodeStatus.failed, error=str(ex), started_at=node_start)
            state.partial = True

    def _node_retrieval(self, state: ReviewState) -> None:
        """Hybrid BM25 + vector KNN + RRF retrieval (A-10).

        For each Unsupported finding, runs a tenant-scoped hybrid search and:
        1. Populates state.retrieval_traces (quote -> trace summary).
        2. Adds matched source IDs to state.matched_sources (I3.4).
        """
        node_start = datetime.utcnow()
        try:
            retriever = self._get_retriever()
            unsupported_findings = [
                f for f in state.findings
                if f.type.value == "unsupported"
            ]

            for finding in unsupported_findings:
                result = retriever.query(
                    query_text=finding.span.quote,
                    tenant_id=state.tenant_id,
                    top_k=5,
                    session=state.session,
                )
                # Store trace for verifier enrichment step
                state.retrieval_traces[finding.span.quote] = result.trace_summary
                # Record all matched sources for impact analysis (PRD I3.4)
                for hit in result.hits:
                    state.matched_sources.add(hit.source_id)

            state.add_progress("retrieval", RunNodeStatus.done, started_at=node_start)
        except Exception as ex:
            state.add_progress("retrieval", RunNodeStatus.failed, error=str(ex), started_at=node_start)
            state.partial = True

    def _node_accessibility_visual(self, state: ReviewState) -> None:
        """Execute multimodal accessibility and visual brand checks (A-14, A-15)."""
        node_start = datetime.utcnow()
        try:
            findings, sources = self.accessibility_checker.check_units(state.units, state.policy)
            state.findings.extend(findings)
            state.matched_sources.update(sources)
            state.add_progress("accessibility_visual", RunNodeStatus.done, started_at=node_start)
        except Exception as ex:
            state.add_progress("accessibility_visual", RunNodeStatus.failed, error=str(ex), started_at=node_start)
            state.partial = True

    def _node_llm(self, state: ReviewState) -> None:
        """Execute tone checker (A-16) and LLM checks with strict policy enforcement (A-06)."""
        node_start = datetime.utcnow()

        # 1. Deterministic tone checker (A-16): sentence stats + rubric/exemplar comparison
        tone_findings = self.tone_checker.check_units(state.units)
        for tf in tone_findings:
            state.findings.append(tf)
            for ev in tf.evidence:
                state.matched_sources.add(ev.source)
            if tf.rule_id:
                state.matched_sources.add(tf.rule_id)

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
        """Citation Verifier node: drops unverified/hallucinated findings (A-11, G2).

        Also enriches Unsupported findings with hybrid retrieval traces.
        """
        node_start = datetime.utcnow()
        try:
            units_by_id = {u.unit_id: u for u in state.units}
            verified_findings, dropped_count, drop_rate = self.verifier.filter_findings(
                state.findings, units_by_id
            )
            # G2: Embed retrieval trace into Unsupported explanations
            verified_findings = self.verifier.enrich_unsupported_with_trace(
                verified_findings, state.retrieval_traces
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

    def _node_abstain(self, state: ReviewState) -> None:
        """Apply abstain rule and route_to enforcement (A-12).

        - Tags ambiguous-rule findings with abstained=True (Needs judgment).
        - Enforces correct route_to per finding type (R1 §2.5).
        - Records every source matched (including Supported) for impact analysis (I3.4).
        """
        node_start = datetime.utcnow()
        try:
            from brand_kit.fixtures import RULES
            from brand_kit.meridian_flow import RuleKind
            ambiguous_rule_ids = {r.rule_id for r in RULES if r.kind == RuleKind.ambiguous}

            # Tag findings that need human judgment
            tagged = self.abstain_router.apply_needs_judgment(
                state.findings, ambiguous_rule_ids
            )
            # Enforce route_to and collect all matched sources
            processed, all_sources = self.abstain_router.process_findings(
                tagged, state.matched_sources, ambiguous_rule_ids
            )
            state.findings = processed
            state.matched_sources = all_sources
            state.add_progress("abstain", RunNodeStatus.done, started_at=node_start)
        except Exception as ex:
            state.add_progress("abstain", RunNodeStatus.failed, error=str(ex), started_at=node_start)
            state.partial = True

    def _node_aggregator(self, state: ReviewState) -> None:
        """Final aggregation, deduplication, and minimal-edit fix generation (A-13, G3, T9)."""
        node_start = datetime.utcnow()
        units_by_id = {u.unit_id: u for u in state.units}
        updated_findings: List[Finding] = []
        seen_ids: Set[str] = set()

        for f in state.findings:
            if f.finding_id in seen_ids:
                continue
            seen_ids.add(f.finding_id)

            # Generate or verify minimal fix
            if f.suggested_fix is None or not f.suggested_fix.rechecked:
                unit = units_by_id.get(f.span.unit_id)
                if unit:
                    fix = generate_minimal_fix(f, unit, state.intent_card, state.policy)
                    if fix:
                        f = f.model_copy(update={"suggested_fix": fix})
            updated_findings.append(f)

        state.findings = updated_findings
        state.add_progress("aggregator", RunNodeStatus.done, started_at=node_start)


# Global default pipeline instance
_DEFAULT_PIPELINE = ReviewPipeline()


def run_review(
    revision_units: List[ContentUnit],
    ruleset_version: int = 1,
    session: Any = None,
    policy: Optional[Sensitivity] = None,
    intent_card: Optional[IntentCard] = None,
    tenant_id: str = "tenant_meridian",
    simulate_llm_failure: bool = False,
    simulate_retrieval_failure: bool = False,
) -> ReviewResult:
    """Real engine entrypoint satisfying Integration Contract T1."""
    state = ReviewState(
        revision_units=revision_units,
        ruleset_version=ruleset_version,
        policy=policy,
        intent_card=intent_card,
        session=session,
        tenant_id=tenant_id,
        simulate_llm_failure=simulate_llm_failure,
        simulate_retrieval_failure=simulate_retrieval_failure,
    )
    return _DEFAULT_PIPELINE.run(state)
