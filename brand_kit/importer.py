"""Idempotent brand kit importer (A-03, Issue #2).

Implements the import logic used by POST /import/brand-kit:
  - Computes a SHA-256 content_hash of the serialised kit.
  - Re-importing an identical kit (same tenant_id + content_hash) is a no-op
    and returns the existing record — it never silently duplicates versions.
  - Returns an ImportResult describing whether the import was new or skipped.
"""

from __future__ import annotations

import hashlib
import json
from typing import Dict, Optional

from brand_kit.models import BrandKit


class ImportResult:
    """Outcome of a brand kit import attempt."""

    def __init__(
        self,
        *,
        tenant_id: str,
        content_hash: str,
        created: bool,
        kit: BrandKit,
    ) -> None:
        self.tenant_id = tenant_id
        self.content_hash = content_hash
        self.created = created  # False → idempotent no-op
        self.kit = kit

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "content_hash": self.content_hash,
            "created": self.created,
            "rule_count": len(self.kit.rules),
            "glossary_count": len(self.kit.glossary),
            "fact_count": len(self.kit.facts),
            "palette_count": len(self.kit.palette),
            "logo_count": len(self.kit.logos),
            "licensed_asset_count": len(self.kit.licensed_assets),
        }


def _compute_hash(kit: BrandKit) -> str:
    """SHA-256 of the canonical JSON representation of the brand kit."""
    canonical = kit.model_dump_json(indent=None)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# In-process store: maps (tenant_id, content_hash) → BrandKit.
# In production Yash's API will persist this to PostgreSQL.  Here it is an
# in-memory dict so the stub FastAPI endpoint and tests can run without a DB.
_IMPORT_STORE: Dict[str, BrandKit] = {}


def import_brand_kit(kit: BrandKit) -> ImportResult:
    """Import a brand kit, returning a no-op result if already imported.

    Args:
        kit: The BrandKit to import.

    Returns:
        ImportResult with created=True on first import, created=False on
        identical re-import (idempotent no-op).
    """
    content_hash = _compute_hash(kit)
    store_key = f"{kit.tenant_id}::{content_hash}"

    if store_key in _IMPORT_STORE:
        # Identical content_hash → idempotent no-op
        return ImportResult(
            tenant_id=kit.tenant_id,
            content_hash=content_hash,
            created=False,
            kit=_IMPORT_STORE[store_key],
        )

    _IMPORT_STORE[store_key] = kit
    return ImportResult(
        tenant_id=kit.tenant_id,
        content_hash=content_hash,
        created=True,
        kit=kit,
    )


def reset_store() -> None:
    """Clear the in-memory store. Used by tests only."""
    _IMPORT_STORE.clear()

