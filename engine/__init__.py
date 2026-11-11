"""Axiom Multimodal Automated Review Engine."""

from engine.abstain import AbstainRouter, apply_needs_judgment, process_findings, route_to_for_type
from engine.accessibility import (
    AccessibilityVisualChecker,
    ContrastChecker,
    OCRValidator,
    PaletteChecker,
    StructureChecker,
    calculate_ciede2000_delta_e,
    calculate_contrast_ratio,
    calculate_relative_luminance,
)
from engine.compiler import GuidelineCompiler, compile
from engine.fact_ledger import ExtractedClaim, RetrievalFailureError, TemporalFactLedger
from engine.intent_card import (
    RecheckReport,
    compute_intent_similarity,
    extract_intent_card,
    generate_minimal_fix,
    recheck_fix,
    recheck_fix_detailed,
)
from engine.llm_client import LLMClient, LLMResponse, PolicyViolationError
from engine.parsers import parse_markdown, parse_text
from engine.pipeline import ReviewPipeline, ReviewState, run_review
from engine.retrieval import HybridRetriever, RetrievalHit, RetrievalResult, SourceRecord, get_default_retriever
from engine.terminology import TerminologyChecker
from engine.tone import ToneChecker
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
    "AccessibilityVisualChecker",
    "ContrastChecker",
    "PaletteChecker",
    "StructureChecker",
    "OCRValidator",
    "calculate_contrast_ratio",
    "calculate_ciede2000_delta_e",
    "calculate_relative_luminance",
    "ToneChecker",
    "extract_intent_card",
    "compute_intent_similarity",
    "generate_minimal_fix",
    "recheck_fix",
    "recheck_fix_detailed",
    "RecheckReport",
]
