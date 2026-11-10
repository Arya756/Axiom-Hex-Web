"""Shared contracts for Axiom (BrandLedger).

These Pydantic models are the single source of truth for the data shapes exchanged
between the engine (Ayush) and the platform (Yash). See PRD §4.4 T1-T9 and
issue_description.md Issue #1.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class FindingType(str, Enum):
    outdated = "outdated"
    contradicted = "contradicted"
    unsupported = "unsupported"
    terminology = "terminology"
    tone = "tone"
    accessibility = "accessibility"
    visual = "visual"


class FindingSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FindingStatus(str, Enum):
    open = "open"
    accepted = "accepted"
    rejected = "rejected"
    overridden = "overridden"
    disputed = "disputed"


class Sensitivity(str, Enum):
    public = "public"
    internal = "internal"
    restricted = "restricted"


class RunNodeStatus(str, Enum):
    queued = "queued"
    running = "running"
    partial = "partial"
    done = "done"
    failed = "failed"


class Method(str, Enum):
    deterministic_lookup = "deterministic_lookup"
    hybrid_retrieval = "hybrid_retrieval"
    llm_assisted = "llm_assisted"
    ocr = "ocr"
    wcag_contrast = "wcag_contrast"
    ciede2000 = "ciede2000"


# ---------------------------------------------------------------------------
# ContentUnit (T2)
# ---------------------------------------------------------------------------


class BBox(BaseModel):
    """Normalized bounding box: [page, x0, y0, x1, y1] in 0.0-1.0 relative coords."""

    page: int = Field(..., ge=0)
    x0: float = Field(..., ge=0.0, le=1.0)
    y0: float = Field(..., ge=0.0, le=1.0)
    x1: float = Field(..., ge=0.0, le=1.0)
    y1: float = Field(..., ge=0.0, le=1.0)


class ContentUnit(BaseModel):
    """A single parsed unit of content (paragraph, span, image region, etc.)."""

    unit_id: str
    revision_id: str
    kind: str  # "text" | "paragraph" | "heading" | "image" | "table"
    text: str
    start: int = Field(..., ge=0)  # char offset in revision text
    end: int = Field(..., ge=0)
    page: Optional[int] = None
    bbox: Optional[BBox] = None
    style: Optional[Dict[str, Any]] = None  # font, size, color, bold, etc.
    alt_text: Optional[str] = None
    source_map: Optional[Dict[str, Any]] = None

    @property
    def offsets(self) -> List[int]:
        """Char offsets as [start, end] for T2 compatibility."""
        return [self.start, self.end]


# ---------------------------------------------------------------------------
# Evidence / SuggestedFix / Disclosure / Span (T3)
# ---------------------------------------------------------------------------


class Span(BaseModel):
    """Exact text span locating a finding in a ContentUnit (T2, T3)."""

    unit_id: str
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)
    quote: str

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class Evidence(BaseModel):
    source: str  # e.g. "F-112"
    version: int
    status: str  # "active" | "superseded"
    current_version: Optional[int] = None
    current_value: Optional[str] = None
    effective: Optional[str] = None  # ISO date


class SuggestedFix(BaseModel):
    text: str
    edit_budget: str = "minimal"  # "minimal" | "moderate"
    rechecked: bool = False
    intent_similarity: Optional[float] = None


class DisclosureRecord(BaseModel):
    method: Method
    provider: Optional[str] = None  # e.g. "openai"
    model: Optional[str] = None  # exact model ID
    external_call: bool = False
    data_categories: List[str] = Field(default_factory=list)
    sensitivity: Sensitivity
    tokens: Optional[int] = None
    cost: Optional[float] = None
    latency_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Finding (T3) — canonical schema
# ---------------------------------------------------------------------------


class Finding(BaseModel):
    finding_id: str
    type: FindingType
    severity: FindingSeverity
    confidence: float = Field(..., ge=0.0, le=1.0)
    span: Span  # exact span locating quote in ContentUnit
    evidence: List[Evidence] = Field(default_factory=list)
    explanation: str
    suggested_fix: Optional[SuggestedFix] = None
    route_to: str  # role queue, e.g. "legal_reviewer"
    disclosure: DisclosureRecord
    status: FindingStatus = FindingStatus.open
    abstained: bool = False  # T8 Radar input (abstain signal)
    rule_id: Optional[str] = None  # T8 Radar input (source rule ID)


# ---------------------------------------------------------------------------
# ReviewResult (T1)
# ---------------------------------------------------------------------------


class RunProgress(BaseModel):
    node: str
    status: RunNodeStatus
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


class ReviewResult(BaseModel):
    revision_id: str
    ruleset_version: int
    sensitivity: Sensitivity
    findings: List[Finding] = Field(default_factory=list)
    matched_sources: List[str] = Field(default_factory=list)  # for impact analysis (T8)
    run_progress: List[RunProgress] = Field(default_factory=list)
    disclosures: List[DisclosureRecord] = Field(default_factory=list)
    partial: bool = False
    cache_key: Optional[str] = None


# ---------------------------------------------------------------------------
# Intent Card (T9 / golden path step 2)
# ---------------------------------------------------------------------------


class IntentCard(BaseModel):
    purpose: str
    audience: str
    key_message: str
    cta: Optional[str] = None


# ---------------------------------------------------------------------------
# Compile Hook Models (T5 / T8)
# ---------------------------------------------------------------------------


class SourceVersion(BaseModel):
    """A source or fact version to be compiled into the Knowledge Base (T5)."""

    source_id: str  # e.g. "F-112", "R-01"
    version: int = Field(..., ge=1)
    kind: str = "rule"  # "rule" | "fact" | "glossary" | "palette"
    body: str
    metadata: Optional[Dict[str, Any]] = None


class CompileResult(BaseModel):
    """Result returned by the guideline compiler on source/version create (T5, T8)."""

    source_id: str
    version: int
    embedding: List[float] = Field(..., description="384-d vector for BAAI/bge-small-en-v1.5")
    lint_flags: List[str] = Field(default_factory=list)
    collisions: List[str] = Field(default_factory=list)
