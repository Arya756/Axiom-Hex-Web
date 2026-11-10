"""FastAPI stub application for Axiom (Issue #2, A1, G0).

Exposes:
  POST /import/brand-kit         — import the Meridian Flow brand kit (idempotent)
  GET  /brand-kit                — retrieve the loaded brand kit summary
  POST /review                   — stub review round-trip (T1 acceptance check)
  GET  /health                   — liveness check

The import endpoint:
  - Accepts the brand kit as JSON
  - Computes a SHA-256 content_hash of the payload
  - Re-importing an identical kit (same content_hash) is a no-op (returns 200 + "no_change")
  - Re-importing a changed kit updates the in-memory store (returns 200 + "updated")

This is the stub FastAPI that proves T1 acceptance:
  "A sample review round-trips through FastAPI and renders in Next.js without manual reshaping."
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from brand_kit.fixtures import MERIDIAN_FLOW_KIT
from brand_kit.models import BrandKit
from contracts.models import (
    ContentUnit,
    IntentCard,
    ReviewResult,
    Sensitivity,
)
from contracts.stub_engine import run_review

app = FastAPI(
    title="Axiom Stub API",
    description="G0 stub: contracts, brand kit import and stub review round-trip (Issue #2).",
    version="0.1.0",
)

# Allow Next.js dev server and any origin in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory store (replaced by real DB in Issue #3/Y-02)
# ---------------------------------------------------------------------------

_store: Dict[str, Any] = {
    "brand_kit": None,
    "content_hash": None,
}


def reset_store() -> None:
    """Clear in-memory store (used for test isolation)."""
    _store["brand_kit"] = None
    _store["content_hash"] = None


def _content_hash(payload: dict) -> str:
    """SHA-256 hash of the JSON-serialised payload (deterministic key ordering)."""
    raw = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Response shapes
# ---------------------------------------------------------------------------


class ImportResponse(BaseModel):
    status: str           # "created" | "no_change" | "updated"
    created: bool = True
    tenant_id: str = "meridian-flow"
    content_hash: str
    rule_count: int = 0
    rules_count: int = 0
    glossary_count: int = 0
    fact_count: int = 0
    facts_count: int = 0
    palette_count: int = 0
    logo_count: int = 0
    logos_count: int = 0
    licensed_asset_count: int = 0
    licensed_assets_count: int = 0


class ReviewRequest(BaseModel):
    revision_id: Optional[str] = None
    units: Optional[list[ContentUnit]] = None
    revision_units: Optional[list[ContentUnit]] = None
    ruleset_version: int = 1
    policy: Sensitivity = Sensitivity.internal
    intent_card: Optional[IntentCard] = None

    @property
    def resolved_units(self) -> list[ContentUnit]:
        return self.revision_units if self.revision_units is not None else (self.units or [])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
@app.get("/healthz")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.post("/import/brand-kit", response_model=ImportResponse)
def import_brand_kit(kit: BrandKit) -> ImportResponse:
    """Import the Meridian Flow brand kit.

    Idempotent: re-importing an identical kit (same SHA-256 content_hash)
    returns status='no_change' without modifying the store.
    """
    payload = kit.model_dump(mode="json")
    new_hash = _content_hash(payload)

    if _store["content_hash"] == new_hash:
        # No-op — identical content
        return ImportResponse(
            status="no_change",
            created=False,
            tenant_id=kit.tenant_id,
            content_hash=new_hash,
            rule_count=len(kit.rules),
            rules_count=len(kit.rules),
            glossary_count=len(kit.glossary),
            fact_count=len(kit.facts),
            facts_count=len(kit.facts),
            palette_count=len(kit.palette),
            logo_count=len(kit.logos),
            logos_count=len(kit.logos),
            licensed_asset_count=len(kit.licensed_assets),
            licensed_assets_count=len(kit.licensed_assets),
        )

    was_empty = _store["brand_kit"] is None
    _store["brand_kit"] = payload
    _store["content_hash"] = new_hash

    return ImportResponse(
        status="created" if was_empty else "updated",
        created=was_empty,
        tenant_id=kit.tenant_id,
        content_hash=new_hash,
        rule_count=len(kit.rules),
        rules_count=len(kit.rules),
        glossary_count=len(kit.glossary),
        fact_count=len(kit.facts),
        facts_count=len(kit.facts),
        palette_count=len(kit.palette),
        logo_count=len(kit.logos),
        logos_count=len(kit.logos),
        licensed_asset_count=len(kit.licensed_assets),
        licensed_assets_count=len(kit.licensed_assets),
    )


@app.get("/brand-kit")
def get_brand_kit() -> dict:
    """Return the currently loaded brand kit summary."""
    if _store["brand_kit"] is None:
        raise HTTPException(status_code=404, detail="No brand kit loaded yet.")
    kit = _store["brand_kit"]
    return {
        "tenant_id": kit["tenant_id"],
        "version": kit["version"],
        "content_hash": _store["content_hash"],
        "rules_count": len(kit["rules"]),
        "glossary_count": len(kit["glossary"]),
        "facts_count": len(kit["facts"]),
        "palette_count": len(kit["palette"]),
        "logos_count": len(kit["logos"]),
        "licensed_assets_count": len(kit["licensed_assets"]),
    }


@app.post("/review", response_model=ReviewResult)
def review(req: ReviewRequest) -> ReviewResult:
    """Stub review round-trip (T1).

    Returns a ReviewResult that Next.js can render without manual reshaping.
    """
    units = req.resolved_units
    if not units:
        raise HTTPException(status_code=422, detail="revision_units must not be empty.")
    return run_review(
        revision_units=units,
        ruleset_version=req.ruleset_version,
        policy=req.policy,
        intent_card=req.intent_card,
    )
