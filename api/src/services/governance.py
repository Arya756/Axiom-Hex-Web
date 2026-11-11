"""Governance services for Y-11..Y-15: routing, audit hash chaining, usage ledger, and settings."""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from api.src.models.workflow import AuditLog, UsageLedger

GENESIS_HASH = "0" * 64

CLAIM_FINDING_TYPES = frozenset({"contradicted", "outdated", "unsupported"})

EXTERNAL_SERVICES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "purpose": "LLM claim extraction, classification, and rewrite suggestions",
        "data_sent": ["document_spans", "source_excerpts"],
        "allowed_sensitivities": ["public", "internal", "confidential"],
        "disabled_on_restricted": True,
    },
    {
        "id": "gemini",
        "name": "Google Gemini API",
        "purpose": "Multimodal visual and accessibility review for image uploads",
        "data_sent": ["uploaded_images", "accessibility_prompts"],
        "allowed_sensitivities": ["public", "internal", "confidential"],
        "disabled_on_restricted": True,
    },
    {
        "id": "local_embeddings",
        "name": "Local Sentence-Transformers / Deterministic Pipeline",
        "purpose": "On-premise embeddings, term matching, regex checks, and claim grounding",
        "data_sent": [],
        "allowed_sensitivities": ["public", "internal", "confidential", "restricted"],
        "disabled_on_restricted": False,
    },
]

_AUDIT_THREAD_LOCK = threading.Lock()


def route_finding_by_type(finding_type: str, abstained: bool = False) -> str:
    """Assign a finding to a reviewer role queue per R1 section 2.5 (Y-12).

    Claim-type findings (contradicted, outdated, unsupported) route to legal_reviewer.
    All brand, style, terminology, accessibility, visual, and judgment findings route to reviewer.
    """
    normalized = (finding_type or "").strip().lower()
    if normalized in CLAIM_FINDING_TYPES:
        return "legal_reviewer"
    return "reviewer"


def _normalize_timestamp(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts_utc = ts.replace(tzinfo=timezone.utc)
    else:
        ts_utc = ts.astimezone(timezone.utc)
    return ts_utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compute_audit_hash(
    prev_hash: str,
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    payload: Optional[Dict[str, Any]],
    timestamp: datetime,
) -> str:
    """Compute canonical SHA-256 hash for an audit_log entry."""
    payload_json = json.dumps(
        payload or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    ts_str = _normalize_timestamp(timestamp)
    preimage = (
        f"{prev_hash}|{tenant_id}|{entity_type}|{entity_id}|{action}|{payload_json}|{ts_str}"
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def append_audit_log(
    db: Session,
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Serialize and append a hash-chained row into audit_log for a tenant (Y-14)."""
    normalized_payload = payload if payload is not None else {}

    with _AUDIT_THREAD_LOCK:
        bind = db.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"),
                {"tenant_id": tenant_id},
            )

        last_entry = (
            db.query(AuditLog)
            .filter(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.id.desc())
            .first()
        )
        prev_hash = last_entry.curr_hash if last_entry else GENESIS_HASH
        now = datetime.now(timezone.utc)
        curr_hash = compute_audit_hash(
            prev_hash=prev_hash,
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            payload=normalized_payload,
            timestamp=now,
        )

        entry = AuditLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            payload=normalized_payload,
            prev_hash=prev_hash,
            curr_hash=curr_hash,
            timestamp=now,
        )
        db.add(entry)
        db.flush()
        return entry


def record_usage_entries(
    db: Session,
    tenant_id: str,
    run_id: str,
    sensitivity: str,
    result: Any,
    enforce_no_external: bool = False,
) -> List[UsageLedger]:
    """Persist UsageLedger telemetry records for a completed review run (Y-15)."""
    effective_sensitivity = "restricted" if enforce_no_external else (sensitivity or "internal")
    raw_disclosures = list(getattr(result, "disclosures", None) or [])

    if not raw_disclosures:
        for finding in getattr(result, "findings", None) or []:
            disc = getattr(finding, "disclosure", None)
            if disc is not None:
                raw_disclosures.append(disc)

    entries: List[UsageLedger] = []

    if not raw_disclosures:
        entry = UsageLedger(
            id=f"usage_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            run_id=run_id,
            node="review_pipeline",
            method="deterministic",
            provider=None,
            model=None,
            external_call=False,
            data_categories=[],
            sensitivity=effective_sensitivity,
            tokens=0,
            cost=0.0,
            latency_ms=0,
        )
        db.add(entry)
        entries.append(entry)
        return entries

    restricted_mode = enforce_no_external or effective_sensitivity == "restricted"

    for disc in raw_disclosures:
        is_external = False if restricted_mode else bool(getattr(disc, "external_call", False))
        tokens = 0 if restricted_mode else int(getattr(disc, "tokens", 0) or 0)
        cost = 0.0 if restricted_mode else float(getattr(disc, "cost", 0.0) or 0.0)
        provider = None if restricted_mode else getattr(disc, "provider", None)
        model = None if restricted_mode else getattr(disc, "model", None)
        raw_method = getattr(disc, "method", None)
        method_str = raw_method.value if hasattr(raw_method, "value") else (raw_method or "deterministic")
        method = "deterministic" if restricted_mode else str(method_str)
        node = getattr(disc, "node", None) or "review_pipeline"
        data_categories = [] if restricted_mode else list(getattr(disc, "data_categories", None) or [])
        latency_ms = int(getattr(disc, "latency_ms", 0) or 0)

        entry = UsageLedger(
            id=f"usage_{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id,
            run_id=run_id,
            node=node,
            method=method,
            provider=provider,
            model=model,
            external_call=is_external,
            data_categories=data_categories,
            sensitivity=effective_sensitivity,
            tokens=tokens,
            cost=cost,
            latency_ms=latency_ms,
        )
        db.add(entry)
        entries.append(entry)

    return entries
