from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from api.src.database import Base


class ReviewRun(Base):
    __tablename__ = "review_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ruleset_version: Mapped[int] = mapped_column(nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    partial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cache_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    matched_sources: Mapped[List[str]] = mapped_column(JSON, default=list)
    run_progress: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class FindingModel(Base):
    __tablename__ = "findings"

    finding_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("review_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    span_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_fix_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    route_to: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rule_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    disclosure_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class FindingDecision(Base):
    __tablename__ = "finding_decisions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("findings.finding_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # accept, reject, override, dispute
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    span_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

