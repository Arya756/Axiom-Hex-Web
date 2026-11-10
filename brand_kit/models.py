"""Pydantic models for the Meridian Flow brand kit (A-03).

These models describe the shape of brand kit objects imported via
POST /import/brand-kit and stored in the Knowledge Base.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RuleKind(str, Enum):
    control = "control"       # Clear, unambiguous rules
    ambiguous = "ambiguous"   # Seeded ambiguous rules (Radar test)


class BrandRule(BaseModel):
    """A single brand guideline rule."""
    rule_id: str             # e.g. "R-01"
    kind: RuleKind
    title: str
    description: str
    owner: Optional[str] = None          # None on ambiguous rules (lint flag)
    good_examples: List[str] = Field(default_factory=list)
    bad_examples: List[str] = Field(default_factory=list)
    collides_with: Optional[str] = None  # e.g. "R-03" for R-16


class GlossaryTerm(BaseModel):
    """A preferred / banned term mapping."""
    term_id: str             # e.g. "G-01"
    preferred: str           # Canonical form
    banned: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class FactVersion(BaseModel):
    """One version of a versioned brand fact."""
    version: int = Field(..., ge=1)
    value: str
    unit: Optional[str] = None
    valid_from: date
    valid_until: Optional[date] = None   # Closed by next version
    superseded_by: Optional[int] = None  # Version number of successor


class BrandFact(BaseModel):
    """A versioned brand fact (Temporal Fact Ledger entry)."""
    fact_id: str             # e.g. "F-112"
    subject: str             # e.g. "customers"
    metric: str              # e.g. "count"
    versions: List[FactVersion]


class PaletteColor(BaseModel):
    """An approved brand palette colour."""
    name: str
    hex: str                 # e.g. "#1A73E8"
    usage: Optional[str] = None


class LogoAsset(BaseModel):
    """A brand logo asset."""
    asset_id: str
    name: str
    path: str                # Relative path in brand_kit/assets/
    formats: List[str]       # e.g. ["svg", "png"]


class LicensedAsset(BaseModel):
    """A licensed asset with an expiry date."""
    asset_id: str
    name: str
    path: str
    license: str
    expires: date            # Expiry date — will be demo week + 2


class BrandKit(BaseModel):
    """Complete Meridian Flow brand kit (A-03)."""
    tenant_id: str = "meridian-flow"
    version: int = 1
    rules: List[BrandRule]
    glossary: List[GlossaryTerm]
    facts: List[BrandFact]
    palette: List[PaletteColor]
    logos: List[LogoAsset]
    licensed_assets: List[LicensedAsset]
