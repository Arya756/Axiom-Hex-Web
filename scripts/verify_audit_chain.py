#!/usr/bin/env python3
"""Standalone cryptographic audit hash-chain verifier for audit_log (Y-14)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.src.config import settings
from api.src.models.workflow import AuditLog
from api.src.services.governance import GENESIS_HASH, compute_audit_hash


def verify_audit_chain(
    db: Session, tenant_id: Optional[str] = None
) -> Tuple[bool, List[str], int]:
    """Walk audit_log ordered by id ASC and verify per-tenant SHA-256 hash links.

    Returns (is_valid, error_messages, verified_row_count).
    """
    query = db.query(AuditLog)
    if tenant_id:
        query = query.filter(AuditLog.tenant_id == tenant_id)

    rows = query.order_by(AuditLog.id.asc()).all()
    expected_prev: Dict[str, str] = {}
    errors: List[str] = []

    for row in rows:
        expected = expected_prev.get(row.tenant_id, GENESIS_HASH)
        if row.prev_hash != expected:
            errors.append(
                f"audit_log.id={row.id} (tenant={row.tenant_id}): prev_hash mismatch "
                f"(expected={expected}, actual={row.prev_hash})"
            )

        recomputed = compute_audit_hash(
            prev_hash=row.prev_hash,
            tenant_id=row.tenant_id,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            action=row.action,
            payload=row.payload,
            timestamp=row.timestamp,
        )
        if row.curr_hash != recomputed:
            errors.append(
                f"audit_log.id={row.id} (tenant={row.tenant_id}): curr_hash mismatch "
                f"(expected={recomputed}, actual={row.curr_hash})"
            )

        expected_prev[row.tenant_id] = row.curr_hash

    return len(errors) == 0, errors, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cryptographically verify the audit_log SHA-256 hash chain."
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("ADMIN_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or settings.ADMIN_DATABASE_URL,
        help="SQLAlchemy database URL (defaults to ADMIN_DATABASE_URL / DATABASE_URL).",
    )
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="Optional tenant_id to restrict verification.",
    )
    args = parser.parse_args()

    engine = create_engine(args.database_url)
    SessionFactory = sessionmaker(bind=engine)
    try:
        with SessionFactory() as db:
            is_valid, errors, count = verify_audit_chain(db, tenant_id=args.tenant_id)
    finally:
        engine.dispose()

    if not is_valid:
        print(f"FAIL: Audit chain verification failed across {count} entries:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"OK: Verified {count} audit_log entries cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

