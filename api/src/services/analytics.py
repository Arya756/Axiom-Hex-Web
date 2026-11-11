"""Analytics services for Issue Y5 (Y-21..Y-24 & I3): Ambiguity Radar, Impact Analysis, Recurring Insights."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.src.models.content import Content, Revision
from api.src.models.review import FindingDecision, FindingModel, ReviewRun
from api.src.models.source import Source, SourceVersion
from api.src.models.workflow import RuleStat

# Ambiguity Radar Thresholds (I3.2)
MIN_SAMPLE_SIZE = 3
LOW_CONFIDENCE_FLOOR = 0.70
OVERRIDE_DISPUTE_RATE_THRESHOLD = 0.30
ABSTAIN_RATE_THRESHOLD = 0.25
LOW_CONF_RATE_THRESHOLD = 0.30
DISAGREEMENT_RATE_THRESHOLD = 0.25
COLLISION_THRESHOLD = 1

CONTROL_RULE_IDS = frozenset({"R-01", "R-02", "R-03", "R-04"})
AMBIGUOUS_RULE_IDS = frozenset({"R-07", "R-11", "R-14", "R-16"})

ACTIVE_IMPACT_STATUSES = frozenset(
    {
        "draft",
        "in_review",
        "Invalidated (New Unapproved Revision)",
        "changes_requested",
    }
)


def _get_or_create_rule_stat(db: Session, tenant_id: str, rule_id: str) -> RuleStat:
    stat = (
        db.query(RuleStat)
        .filter(RuleStat.tenant_id == tenant_id, RuleStat.rule_id == rule_id)
        .first()
    )
    if stat:
        return stat

    stat = RuleStat(
        id=f"rs_{tenant_id}_{rule_id}",
        tenant_id=tenant_id,
        rule_id=rule_id,
        total_findings=0,
        accepted_count=0,
        disputed_count=0,
        overridden_count=0,
        abstained_count=0,
        low_confidence_count=0,
    )
    db.add(stat)
    db.flush()
    return stat


def sync_rule_stat_for_finding(
    db: Session,
    tenant_id: str,
    rule_id: Optional[str],
    confidence: float,
    abstained: bool,
) -> Optional[RuleStat]:
    """Increment rule_stats counters when a finding with a rule_id is persisted."""
    if not rule_id:
        return None
    stat = _get_or_create_rule_stat(db, tenant_id, rule_id)
    stat.total_findings += 1
    if abstained:
        stat.abstained_count += 1
    if confidence < LOW_CONFIDENCE_FLOOR:
        stat.low_confidence_count += 1
    stat.updated_at = datetime.now(timezone.utc)
    return stat


def sync_rule_stat_for_decision(
    db: Session,
    tenant_id: str,
    finding: FindingModel,
    action: str,
) -> Optional[RuleStat]:
    """Update rule_stats decision counters when a FindingDecision is recorded."""
    if not finding.rule_id:
        return None
    stat = _get_or_create_rule_stat(db, tenant_id, finding.rule_id)
    if stat.total_findings == 0:
        stat.total_findings = (
            db.query(FindingModel)
            .filter(
                FindingModel.tenant_id == tenant_id,
                FindingModel.rule_id == finding.rule_id,
            )
            .count()
        )
    normalized = action.lower().strip()
    if normalized == "accept":
        stat.accepted_count += 1
    elif normalized == "override":
        stat.overridden_count += 1
    elif normalized == "dispute":
        stat.disputed_count += 1
    stat.updated_at = datetime.now(timezone.utc)
    return stat


def _is_synthetic_finding(finding: FindingModel) -> bool:
    disc = finding.disclosure_json or {}
    if isinstance(disc, dict) and disc.get("synthetic") is True:
        return True
    if finding.finding_id.startswith("f_syn_"):
        return True
    return False


def _extract_rule_metadata(
    db: Session, tenant_id: str
) -> Dict[str, Dict[str, Any]]:
    """Collect active rule definitions, lint flags, and collisions from sources/source_versions."""
    rules_by_id: Dict[str, Dict[str, Any]] = {}
    rule_sources = (
        db.query(Source)
        .filter(Source.tenant_id == tenant_id, Source.kind == "rule")
        .all()
    )
    for src in rule_sources:
        latest_sv = (
            db.query(SourceVersion)
            .filter(
                SourceVersion.tenant_id == tenant_id,
                SourceVersion.source_id == src.id,
            )
            .order_by(SourceVersion.version.desc())
            .first()
        )
        lint_flags = list(latest_sv.lint_flags or []) if latest_sv else []
        collisions = list(latest_sv.collisions or []) if latest_sv else []
        meta = dict(latest_sv.metadata_json or {}) if latest_sv else {}

        collides_with = meta.get("collides_with")
        if collides_with and collides_with not in collisions:
            collisions.append(str(collides_with))

        missing_owner = bool(meta.get("missing_owner")) or ("missing_owner" in lint_flags)
        missing_examples = bool(meta.get("missing_examples")) or ("missing_examples" in lint_flags)

        rules_by_id[src.id] = {
            "rule_id": src.id,
            "rule_name": src.name,
            "rule_description": src.description,
            "rule_body": latest_sv.body if latest_sv else (src.description or src.name),
            "current_version": src.current_version,
            "lint_flags": lint_flags,
            "collisions": collisions,
            "collision_count": len(collisions),
            "missing_owner": missing_owner,
            "missing_examples": missing_examples,
            "metadata": meta,
        }
    return rules_by_id


def get_ambiguity_radar(db: Session, tenant_id: str) -> Dict[str, Any]:
    """Execute SQL signal aggregations on rule_stats + live tables for the Ambiguity Radar (Y-21, I3)."""
    # 1. PostgreSQL-compatible GROUP BY aggregation over rule_stats
    stat_rows = (
        db.query(
            RuleStat.rule_id.label("rule_id"),
            func.coalesce(func.sum(RuleStat.total_findings), 0).label("total_findings"),
            func.coalesce(func.sum(RuleStat.accepted_count), 0).label("accepted_count"),
            func.coalesce(func.sum(RuleStat.disputed_count), 0).label("disputed_count"),
            func.coalesce(func.sum(RuleStat.overridden_count), 0).label("overridden_count"),
            func.coalesce(func.sum(RuleStat.abstained_count), 0).label("abstained_count"),
            func.coalesce(func.sum(RuleStat.low_confidence_count), 0).label("low_confidence_count"),
        )
        .filter(RuleStat.tenant_id == tenant_id)
        .group_by(RuleStat.rule_id)
        .all()
    )
    stats_map: Dict[str, Dict[str, int]] = {
        row.rule_id: {
            "total_findings": int(row.total_findings or 0),
            "accepted_count": int(row.accepted_count or 0),
            "disputed_count": int(row.disputed_count or 0),
            "overridden_count": int(row.overridden_count or 0),
            "abstained_count": int(row.abstained_count or 0),
            "low_confidence_count": int(row.low_confidence_count or 0),
        }
        for row in stat_rows
    }

    # 2. Rule definitions + ingest collisions/lint flags
    rule_defs = _extract_rule_metadata(db, tenant_id)

    # 3. Live findings + decisions for disagreement computation and evidence examples
    all_findings = (
        db.query(FindingModel)
        .filter(
            FindingModel.tenant_id == tenant_id,
            FindingModel.rule_id.isnot(None),
        )
        .order_by(FindingModel.created_at.desc())
        .all()
    )
    findings_by_rule: Dict[str, List[FindingModel]] = defaultdict(list)
    finding_id_to_rule: Dict[str, str] = {}
    for f in all_findings:
        if f.rule_id:
            findings_by_rule[f.rule_id].append(f)
            finding_id_to_rule[f.finding_id] = f.rule_id

    all_decisions = (
        db.query(FindingDecision)
        .filter(FindingDecision.tenant_id == tenant_id)
        .order_by(FindingDecision.created_at.asc())
        .all()
    )
    decisions_by_finding: Dict[str, List[FindingDecision]] = defaultdict(list)
    for d in all_decisions:
        decisions_by_finding[d.finding_id].append(d)

    candidate_rule_ids = sorted(
        set(rule_defs.keys()) | set(stats_map.keys()) | set(findings_by_rule.keys())
    )

    radar_rules: List[Dict[str, Any]] = []
    total_synthetic_findings = 0
    total_live_findings = 0

    for rule_id in candidate_rule_ids:
        meta_info = rule_defs.get(
            rule_id,
            {
                "rule_id": rule_id,
                "rule_name": rule_id,
                "rule_description": "",
                "rule_body": "",
                "current_version": 1,
                "lint_flags": [],
                "collisions": [],
                "collision_count": 0,
                "missing_owner": False,
                "missing_examples": False,
                "metadata": {},
            },
        )
        rule_findings = findings_by_rule.get(rule_id, [])
        stat_counts = stats_map.get(rule_id, {})

        # Reconcile rule_stats counters with live findings when rule_stats was not yet incremented
        live_total = len(rule_findings)
        total_findings = max(stat_counts.get("total_findings", 0), live_total)

        live_abstained = sum(1 for f in rule_findings if f.abstained)
        live_low_conf = sum(1 for f in rule_findings if f.confidence < LOW_CONFIDENCE_FLOOR)

        # Count decisions & reviewer disagreements from finding_decisions
        live_accept = 0
        live_override = 0
        live_dispute = 0
        finding_conflicts = 0
        decided_findings_count = 0

        for f in rule_findings:
            f_decs = decisions_by_finding.get(f.finding_id, [])
            if f_decs:
                decided_findings_count += 1
            distinct_actions = {d.action.lower() for d in f_decs}
            if len(distinct_actions) > 1:
                finding_conflicts += 1
            for d in f_decs:
                act = d.action.lower()
                if act == "accept":
                    live_accept += 1
                elif act == "override":
                    live_override += 1
                elif act == "dispute":
                    live_dispute += 1

        accepted_count = max(stat_counts.get("accepted_count", 0), live_accept)
        overridden_count = max(stat_counts.get("overridden_count", 0), live_override)
        disputed_count = max(stat_counts.get("disputed_count", 0), live_dispute)
        abstained_count = max(stat_counts.get("abstained_count", 0), live_abstained)
        low_confidence_count = max(stat_counts.get("low_confidence_count", 0), live_low_conf)

        synthetic_count = sum(1 for f in rule_findings if _is_synthetic_finding(f))
        live_count = max(0, total_findings - synthetic_count)
        total_synthetic_findings += synthetic_count
        total_live_findings += live_count

        # Disagreement count: conflicting decisions on same findings + cross-reviewer split
        disagreement_count = finding_conflicts
        if disagreement_count == 0 and accepted_count > 0 and (overridden_count + disputed_count) > 0:
            # Measure cross-finding split only when significant opposing decisions exist
            minority = min(accepted_count, overridden_count + disputed_count)
            total_dec = accepted_count + overridden_count + disputed_count
            if total_dec > 0 and (minority / total_dec) >= DISAGREEMENT_RATE_THRESHOLD:
                disagreement_count = minority

        denom = max(total_findings, 1)
        decision_denom = max(decided_findings_count, total_findings, 1)

        override_dispute_rate = (
            round((overridden_count + disputed_count) / denom, 4) if total_findings > 0 else 0.0
        )
        abstain_rate = round(abstained_count / denom, 4) if total_findings > 0 else 0.0
        low_confidence_rate = (
            round(low_confidence_count / denom, 4) if total_findings > 0 else 0.0
        )
        disagreement_rate = (
            round(disagreement_count / decision_denom, 4) if total_findings > 0 else 0.0
        )

        collision_count = int(meta_info["collision_count"])
        missing_owner = bool(meta_info["missing_owner"])
        missing_examples = bool(meta_info["missing_examples"])

        flag_reasons: List[str] = []
        if collision_count >= COLLISION_THRESHOLD:
            flag_reasons.append(
                f"Ingest collision with {', '.join(meta_info['collisions'])}"
            )

        if total_findings >= MIN_SAMPLE_SIZE:
            if override_dispute_rate >= OVERRIDE_DISPUTE_RATE_THRESHOLD:
                flag_reasons.append(
                    f"High override/dispute rate ({round(override_dispute_rate * 100)}% across {total_findings} findings)"
                )
            if abstain_rate >= ABSTAIN_RATE_THRESHOLD:
                flag_reasons.append(
                    f"High abstain rate ({round(abstain_rate * 100)}%)"
                )
            if low_confidence_rate >= LOW_CONF_RATE_THRESHOLD:
                flag_reasons.append(
                    f"Low average confidence (<{LOW_CONFIDENCE_FLOOR:.2f} on {low_confidence_count}/{total_findings} findings)"
                )
            if disagreement_rate >= DISAGREEMENT_RATE_THRESHOLD:
                flag_reasons.append(
                    f"Reviewer disagreement ({disagreement_count} conflicting finding decisions)"
                )
            if missing_owner and missing_examples:
                flag_reasons.append("Missing rule owner & usage examples at ingest")
        elif missing_owner and missing_examples and total_findings > 0:
            flag_reasons.append("Missing rule owner & usage examples with findings")

        flagged = len(flag_reasons) > 0

        # Composite ambiguity score in [0.0, 1.0] for ranking
        raw_score = (
            0.35 * override_dispute_rate
            + 0.25 * max(abstain_rate, low_confidence_rate)
            + 0.25 * disagreement_rate
            + (0.25 if collision_count > 0 else 0.0)
            + (0.10 if (missing_owner or missing_examples) else 0.0)
        )
        ambiguity_score = round(min(1.0, raw_score), 3)

        # Build concrete evidence examples (I3.2: show counts and example findings, not just a score)
        examples: List[Dict[str, Any]] = []
        for f in rule_findings[:3]:
            f_decs = [
                {
                    "action": d.action,
                    "user_id": d.user_id,
                    "reason": d.reason,
                }
                for d in decisions_by_finding.get(f.finding_id, [])
            ]
            span = f.span_json or {}
            examples.append(
                {
                    "finding_id": f.finding_id,
                    "revision_id": f.revision_id,
                    "type": f.type,
                    "severity": f.severity,
                    "confidence": round(float(f.confidence), 3),
                    "abstained": bool(f.abstained),
                    "status": f.status,
                    "quote": span.get("quote", ""),
                    "explanation": f.explanation,
                    "is_synthetic": _is_synthetic_finding(f),
                    "decisions": f_decs,
                }
            )

        data_origin = "live"
        if synthetic_count > 0 and live_count > 0:
            data_origin = "mixed"
        elif synthetic_count > 0:
            data_origin = "synthetic"

        radar_rules.append(
            {
                "rule_id": rule_id,
                "rule_name": meta_info["rule_name"],
                "rule_body": meta_info["rule_body"],
                "current_version": meta_info["current_version"],
                "flagged": flagged,
                "ambiguity_score": ambiguity_score,
                "flag_reasons": flag_reasons,
                "is_control": rule_id in CONTROL_RULE_IDS or bool(meta_info["metadata"].get("is_control")),
                "is_synthetic": synthetic_count > 0,
                "data_origin": data_origin,
                "signals": {
                    "total_findings": total_findings,
                    "accepted_count": accepted_count,
                    "overridden_count": overridden_count,
                    "disputed_count": disputed_count,
                    "abstained_count": abstained_count,
                    "low_confidence_count": low_confidence_count,
                    "disagreement_count": disagreement_count,
                    "collision_count": collision_count,
                    "collisions": meta_info["collisions"],
                    "lint_flags": meta_info["lint_flags"],
                    "missing_owner": missing_owner,
                    "missing_examples": missing_examples,
                    "synthetic_count": synthetic_count,
                    "live_count": live_count,
                    "override_dispute_rate": override_dispute_rate,
                    "abstain_rate": abstain_rate,
                    "low_confidence_rate": low_confidence_rate,
                    "disagreement_rate": disagreement_rate,
                },
                "example_findings": examples,
            }
        )

    radar_rules.sort(key=lambda r: (not r["flagged"], -r["ambiguity_score"], r["rule_id"]))

    control_rules = [r for r in radar_rules if r["is_control"]]
    false_flagged_controls = [r["rule_id"] for r in control_rules if r["flagged"]]
    false_flag_rate = (
        round(len(false_flagged_controls) / len(control_rules), 4)
        if control_rules
        else 0.0
    )

    seeded_ambiguous = [r for r in radar_rules if r["rule_id"] in AMBIGUOUS_RULE_IDS]
    flagged_ambiguous = [r["rule_id"] for r in seeded_ambiguous if r["flagged"]]

    overall_origin = "live"
    if total_synthetic_findings > 0 and total_live_findings > 0:
        overall_origin = "mixed"
    elif total_synthetic_findings > 0:
        overall_origin = "synthetic"

    return {
        "tenant_id": tenant_id,
        "summary": {
            "total_rules_evaluated": len(radar_rules),
            "flagged_count": sum(1 for r in radar_rules if r["flagged"]),
            "seeded_ambiguous_flagged_count": len(flagged_ambiguous),
            "seeded_ambiguous_total": len(seeded_ambiguous),
            "control_rules_evaluated": len(control_rules),
            "false_flags": len(false_flagged_controls),
            "false_flagged_rule_ids": false_flagged_controls,
            "false_flag_rate": false_flag_rate,
            "total_synthetic_findings": total_synthetic_findings,
            "total_live_findings": total_live_findings,
            "contains_synthetic": total_synthetic_findings > 0,
            "data_origin": overall_origin,
        },
        "thresholds": {
            "min_sample_size": MIN_SAMPLE_SIZE,
            "override_dispute_rate": OVERRIDE_DISPUTE_RATE_THRESHOLD,
            "abstain_rate": ABSTAIN_RATE_THRESHOLD,
            "low_confidence_floor": LOW_CONFIDENCE_FLOOR,
            "low_confidence_rate": LOW_CONF_RATE_THRESHOLD,
            "disagreement_rate": DISAGREEMENT_RATE_THRESHOLD,
            "collision_count": COLLISION_THRESHOLD,
        },
        "rules": radar_rules,
    }


def get_impact_analysis(db: Session, tenant_id: str, source_id: str) -> Dict[str, Any]:
    """Find draft and in-review items whose latest run referenced source_id (Y-22, I3.3, I3.4)."""
    source = (
        db.query(Source)
        .filter(Source.tenant_id == tenant_id, Source.id == source_id)
        .first()
    )

    contents = db.query(Content).filter(Content.tenant_id == tenant_id).all()
    affected_items: List[Dict[str, Any]] = []

    for content in contents:
        latest_rev = (
            db.query(Revision)
            .filter(Revision.tenant_id == tenant_id, Revision.content_id == content.id)
            .order_by(Revision.version_num.desc())
            .first()
        )
        if not latest_rev or latest_rev.status not in ACTIVE_IMPACT_STATUSES:
            continue

        latest_run = (
            db.query(ReviewRun)
            .filter(
                ReviewRun.tenant_id == tenant_id,
                ReviewRun.revision_id == latest_rev.id,
                ReviewRun.status.in_(["done", "partial"]),
            )
            .order_by(ReviewRun.started_at.desc())
            .first()
        )
        if not latest_run:
            continue

        matched_sources = [str(s) for s in (latest_run.matched_sources or [])]
        run_findings = (
            db.query(FindingModel)
            .filter(
                FindingModel.tenant_id == tenant_id,
                FindingModel.run_id == latest_run.id,
            )
            .all()
        )

        cited_count = 0
        for f in run_findings:
            if f.rule_id == source_id:
                cited_count += 1
                continue
            for ev in f.evidence_json or []:
                if isinstance(ev, dict) and (
                    ev.get("source") == source_id or ev.get("source_id") == source_id
                ):
                    cited_count += 1
                    break

        is_in_matched_sources = source_id in matched_sources
        if not is_in_matched_sources and cited_count == 0:
            continue

        matched_via = "finding_evidence" if cited_count > 0 else "supported_claim"
        affected_items.append(
            {
                "content_id": content.id,
                "title": content.title,
                "file_type": content.file_type,
                "revision_id": latest_rev.id,
                "version_num": latest_rev.version_num,
                "revision_status": latest_rev.status,
                "approval_status": latest_rev.approval_status,
                "sensitivity": content.sensitivity,
                "latest_run_id": latest_run.id,
                "latest_run_status": latest_run.status,
                "matched_via": matched_via,
                "findings_for_source_count": cited_count,
                "last_checked_at": (latest_run.finished_at or latest_run.started_at),
            }
        )

    affected_items.sort(key=lambda item: item["title"].lower())
    return {
        "source_id": source_id,
        "source_name": source.name if source else source_id,
        "source_kind": source.kind if source else None,
        "current_version": source.current_version if source else None,
        "affected_count": len(affected_items),
        "affected_items": affected_items,
    }


def get_recurring_insights(db: Session, tenant_id: str) -> Dict[str, Any]:
    """Aggregate common workflow violations, types, severities, and hotspots (Y-23)."""
    findings = (
        db.query(FindingModel)
        .filter(FindingModel.tenant_id == tenant_id)
        .all()
    )
    rule_names = {
        s.id: s.name
        for s in db.query(Source)
        .filter(Source.tenant_id == tenant_id, Source.kind == "rule")
        .all()
    }
    rev_to_content = {
        r.id: r.content_id
        for r in db.query(Revision).filter(Revision.tenant_id == tenant_id).all()
    }
    content_titles = {
        c.id: c.title
        for c in db.query(Content).filter(Content.tenant_id == tenant_id).all()
    }

    by_rule: Dict[str, Dict[str, Any]] = {}
    by_type_counts: Dict[str, int] = defaultdict(int)
    by_severity_counts: Dict[str, int] = defaultdict(int)
    by_content: Dict[str, Dict[str, Any]] = {}

    open_count = 0
    accepted_count = 0
    overridden_count = 0
    disputed_count = 0
    rejected_count = 0
    synthetic_count = 0
    live_count = 0

    for f in findings:
        is_syn = _is_synthetic_finding(f)
        if is_syn:
            synthetic_count += 1
        else:
            live_count += 1

        by_type_counts[f.type] += 1
        by_severity_counts[f.severity] += 1

        if f.status == "open":
            open_count += 1
        elif f.status == "accepted":
            accepted_count += 1
        elif f.status == "overridden":
            overridden_count += 1
        elif f.status == "disputed":
            disputed_count += 1
        elif f.status == "rejected":
            rejected_count += 1

        rid = f.rule_id or "UNSPECIFIED"
        if rid not in by_rule:
            by_rule[rid] = {
                "rule_id": rid,
                "rule_name": rule_names.get(rid, rid),
                "total_count": 0,
                "open_count": 0,
                "accepted_count": 0,
                "overridden_count": 0,
                "disputed_count": 0,
                "synthetic_count": 0,
                "live_count": 0,
                "_conf_sum": 0.0,
            }
        bucket = by_rule[rid]
        bucket["total_count"] += 1
        bucket["_conf_sum"] += float(f.confidence)
        if f.status == "open":
            bucket["open_count"] += 1
        elif f.status == "accepted":
            bucket["accepted_count"] += 1
        elif f.status == "overridden":
            bucket["overridden_count"] += 1
        elif f.status == "disputed":
            bucket["disputed_count"] += 1
        if is_syn:
            bucket["synthetic_count"] += 1
        else:
            bucket["live_count"] += 1

        cid = rev_to_content.get(f.revision_id)
        if cid:
            if cid not in by_content:
                by_content[cid] = {
                    "content_id": cid,
                    "title": content_titles.get(cid, cid),
                    "total_findings": 0,
                    "open_findings": 0,
                    "is_synthetic": False,
                }
            c_bucket = by_content[cid]
            c_bucket["total_findings"] += 1
            if f.status == "open":
                c_bucket["open_findings"] += 1
            if is_syn:
                c_bucket["is_synthetic"] = True

    top_rules = []
    for item in by_rule.values():
        total_c = item["total_count"]
        avg_conf = round(item.pop("_conf_sum") / total_c, 3) if total_c > 0 else 0.0
        item["avg_confidence"] = avg_conf
        item["is_synthetic"] = item["synthetic_count"] > 0
        top_rules.append(item)
    top_rules.sort(key=lambda r: (-r["total_count"], r["rule_id"]))

    total_all = len(findings)
    by_type = [
        {
            "type": k,
            "count": v,
            "share": round(v / total_all, 4) if total_all > 0 else 0.0,
        }
        for k, v in sorted(by_type_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    by_severity = [
        {"severity": k, "count": by_severity_counts.get(k, 0)}
        for k in ("critical", "high", "medium", "low")
    ]
    top_content = sorted(
        by_content.values(),
        key=lambda c: (-c["total_findings"], c["title"].lower()),
    )[:10]

    resolved_count = total_all - open_count
    resolution_rate = round(resolved_count / total_all, 4) if total_all > 0 else 0.0

    return {
        "tenant_id": tenant_id,
        "summary": {
            "total_findings": total_all,
            "open_findings": open_count,
            "resolved_findings": resolved_count,
            "resolution_rate": resolution_rate,
            "accepted_count": accepted_count,
            "overridden_count": overridden_count,
            "disputed_count": disputed_count,
            "rejected_count": rejected_count,
            "synthetic_findings": synthetic_count,
            "live_findings": live_count,
            "contains_synthetic": synthetic_count > 0,
        },
        "top_violated_rules": top_rules,
        "by_type": by_type,
        "by_severity": by_severity,
        "top_affected_content": top_content,
    }

