"""Axiom Multimodal Automated Review Engine."""

from engine.abstain import AbstainRouter, apply_needs_judgment, process_findings, route_to_for_type
from engine.compiler import GuidelineCompiler, compile
from engine.fact_ledger import ExtractedClaim, RetrievalFailureError, TemporalFactLedger
from engine.llm_client import LLMClient, LLMResponse, PolicyViolationError
from engine.parsers import parse_markdown, parse_text
from engine.pipeline import ReviewPipeline, ReviewState, run_review
from engine.retrieval import HybridRetriever, RetrievalHit, RetrievalResult, SourceRecord, get_default_retriever
from engine.terminology import TerminologyChecker
from engine.verifier import CitationVerifier

__all__ = [
    "AbstainRouter",
    "apply_needs_judgment",
    "process_findings",
    "route_to_for_type",
    "GuidelineCompiler",
    "compile",
    "ExtractedClaim",
    "RetrievalFailureError",
    "TemporalFactLedger",
    "LLMClient",
    "LLMResponse",
    "PolicyViolationError",
    "parse_markdown",
    "parse_text",
    "ReviewPipeline",
    "ReviewState",
    "run_review",
    "HybridRetriever",
    "RetrievalHit",
    "RetrievalResult",
    "SourceRecord",
    "get_default_retriever",
    "TerminologyChecker",
    "CitationVerifier",
]
