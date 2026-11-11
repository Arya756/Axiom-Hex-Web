#!/usr/bin/env python3
"""Standalone synthetic decision history generator (Y-24 & I3.5).

Generates synthetic review findings and multi-reviewer decisions strictly through
real FastAPI endpoints (never injecting rows directly into PostgreSQL/SQLite),
so Ambiguity Radar and Recurring Insights can be calibrated and clearly labelled
as synthetic in the UI.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


SYNTHETIC_RULES_CATALOG: List[Dict[str, Any]] = [
    {
        "source_id": "R-01",
        "kind": "rule",
        "name": "Product Terminology",
        "description": "Always use 'Meridian Flow Platform', never abbreviate to 'MFP'.",
        "body": "The company flagship offering must always be referred to as 'Meridian Flow Platform'. Never use the abbreviation 'MFP'.",
        "metadata_json": {"is_control": True, "owner": "brand-ops", "examples": ["Use Meridian Flow Platform"]},
    },
    {
        "source_id": "R-02",
        "kind": "rule",
        "name": "Text Contrast Standards",
        "description": "Text contrast must meet WCAG 2.2 AA (4.5:1 / 3:1).",
        "body": "Text contrast must meet WCAG 2.2 AA minimum standards: 4.5:1 for regular text and 3:1 for large text.",
        "metadata_json": {"is_control": True, "owner": "design-systems", "examples": ["#0F172A on #FFFFFF"]},
    },
    {
        "source_id": "R-03",
        "kind": "rule",
        "name": "Claims Verification Policy",
        "description": "Customer counts and statistics must be substantiated.",
        "body": "All quantitative claims including customer count and uptime percentage must match verified records in the Temporal Fact Ledger.",
        "metadata_json": {"is_control": True, "owner": "legal-compliance", "examples": ["25,000+ enterprise customers (F-112 v3)"]},
    },
    {
        "source_id": "R-04",
        "kind": "rule",
        "name": "Clear and Direct Tone",
        "description": "Communicate clearly, accurately, and professionally.",
        "body": "Communications must be concise, professional, and direct. Avoid clickbait and exaggerated claims.",
        "metadata_json": {"is_control": True, "owner": "editorial-lead", "examples": ["Schedule an enterprise demo"]},
    },
    {
        "source_id": "R-07",
        "kind": "rule",
        "name": "Confident Tone",
        "description": "Ambiguous: confident but humble (missing owner/examples)",
        "body": "Express brand messaging in a voice that is confident but humble.",
        "metadata_json": {"missing_owner": True, "missing_examples": True},
    },
    {
        "source_id": "R-11",
        "kind": "rule",
        "name": "Plain Language",
        "description": "Ambiguous: avoid jargon where possible (high abstain rate)",
        "body": "Avoid technical jargon where possible, except when addressing specialized architects.",
        "metadata_json": {"high_abstain": True, "owner": "editorial-lead"},
    },
    {
        "source_id": "R-14",
        "kind": "rule",
        "name": "Authentic Imagery",
        "description": "Ambiguous: imagery that feels authentic (reviewer disagreement)",
        "body": "Use imagery that feels authentic and human-centric rather than sterile corporate stock photography.",
        "metadata_json": {"disagreement_risk": True, "owner": "brand-design"},
    },
    {
        "source_id": "R-16",
        "kind": "rule",
        "name": "Scale Representation",
        "description": "Ambiguous: don't overstate scale (collides with R-03)",
        "body": "Do not overstate company or customer scale in product descriptions.",
        "metadata_json": {"collides_with": "R-03", "owner": "brand-ops"},
    },
]


def _login(client: Any, email: str, password: str) -> Dict[str, str]:
    resp = client.post("/auth/login", json={"email": email, "password": password})
    if resp.status_code != 200:
        raise RuntimeError(f"Login failed for {email}: {resp.status_code} {resp.text}")
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _ensure_rules_seeded(client: Any, admin_hdrs: Dict[str, str]) -> None:
    resp = client.get("/sources?kind=rule", headers=admin_hdrs)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to list rules: {resp.status_code} {resp.text}")
    existing_ids = {s["id"] for s in resp.json()}

    for rule in SYNTHETIC_RULES_CATALOG:
        if rule["source_id"] in existing_ids:
            continue
        create_resp = client.post("/sources", json=rule, headers=admin_hdrs)
        if create_resp.status_code not in (200, 201):
            raise RuntimeError(
                f"Failed to create rule {rule['source_id']}: {create_resp.status_code} {create_resp.text}"
            )


def _build_synthetic_plan() -> List[Dict[str, Any]]:
    """Build deterministic calibration scenarios for 4 clear control rules and 4 ambiguous rules."""
    scenarios: List[Dict[str, Any]] = []

    # 4 clear control rules (R-01..R-04): high confidence, unanimous acceptance -> 0 false flags
    control_specs = [
        ("R-01", "terminology", "MFP Cloud Sync", "Avoid prohibited abbreviation 'MFP'."),
        ("R-02", "accessibility", "Low contrast caption #888", "Sub-threshold WCAG AA text contrast."),
        ("R-03", "contradicted", "Over 10,000+ users", "Superseded customer count against F-112."),
        ("R-04", "tone", "UNBELIEVABLE #1 DEAL", "Clickbait framing violates R-04 direct tone."),
    ]
    for rule_id, ftype, quote, explanation in control_specs:
        signals = [
            {
                "rule_id": rule_id,
                "type": ftype,
                "severity": "medium",
                "confidence": 0.94,
                "abstained": False,
                "quote": quote,
                "explanation": f"[SYNTHETIC] {explanation}",
                "matched_sources": [rule_id],
            }
            for _ in range(4)
        ]
        # Unanimous single accept per finding
        decision_plan = [[{"role": "legal_reviewer" if ftype == "contradicted" else "reviewer", "action": "accept"}]] * 4
        scenarios.append(
            {
                "label": f"{rule_id}-control",
                "text": f"[SYNTHETIC] Calibration batch for {rule_id}: {quote}.",
                "signals": signals,
                "decision_plan": decision_plan,
            }
        )

    # 4 seeded ambiguous rules (R-07, R-11, R-14, R-16)
    # R-07: missing owner/examples + high override rate (75%) + low confidence (~0.62)
    scenarios.append(
        {
            "label": "R-07-ambiguous",
            "text": "[SYNTHETIC] Calibration batch for R-07: Confident yet humble enterprise narrative.",
            "signals": [
                {
                    "rule_id": "R-07",
                    "type": "tone",
                    "severity": "low",
                    "confidence": 0.61,
                    "abstained": False,
                    "quote": "We lead compliance transformation effortlessly",
                    "explanation": "[SYNTHETIC] Tone borders on boastful under R-07.",
                    "matched_sources": ["R-07"],
                }
                for _ in range(4)
            ],
            "decision_plan": [
                [{"role": "reviewer", "action": "override", "reason": "[SYNTHETIC] Standard executive tone acceptable without R-07 examples."}],
                [{"role": "reviewer", "action": "override", "reason": "[SYNTHETIC] No rule owner clarified humble threshold."}],
                [{"role": "reviewer", "action": "dispute", "reason": "[SYNTHETIC] Subjective wording under R-07."}],
                [{"role": "reviewer", "action": "accept"}],
            ],
        }
    )

    # R-11: high abstain rate (75%) + disputes
    scenarios.append(
        {
            "label": "R-11-ambiguous",
            "text": "[SYNTHETIC] Calibration batch for R-11: Kubernetes RBAC mTLS architecture brief.",
            "signals": [
                {
                    "rule_id": "R-11",
                    "type": "terminology",
                    "severity": "low",
                    "confidence": 0.51 if i < 3 else 0.74,
                    "abstained": True if i < 3 else False,
                    "quote": "Idempotent mTLS ingress controller",
                    "explanation": "[SYNTHETIC] Uncertain whether specialized audience permits technical jargon under R-11.",
                    "matched_sources": ["R-11"],
                }
                for i in range(4)
            ],
            "decision_plan": [
                [{"role": "reviewer", "action": "dispute", "reason": "[SYNTHETIC] Target audience is DevSecOps architects; R-11 unclear."}],
                [{"role": "reviewer", "action": "override", "reason": "[SYNTHETIC] Technical term required for accuracy."}],
                [{"role": "reviewer", "action": "accept"}],
                [{"role": "reviewer", "action": "accept"}],
            ],
        }
    )

    # R-14: high reviewer disagreement (conflicting accept vs dispute/override on identical findings)
    scenarios.append(
        {
            "label": "R-14-ambiguous",
            "text": "[SYNTHETIC] Calibration batch for R-14: Hero banner photography review.",
            "signals": [
                {
                    "rule_id": "R-14",
                    "type": "visual",
                    "severity": "medium",
                    "confidence": 0.64,
                    "abstained": False,
                    "quote": "Team workshop whiteboard portrait",
                    "explanation": "[SYNTHETIC] Evaluates authentic imagery criteria under R-14.",
                    "matched_sources": ["R-14"],
                }
                for _ in range(4)
            ],
            "decision_plan": [
                [
                    {"role": "reviewer", "action": "accept"},
                    {"role": "admin", "action": "dispute", "reason": "[SYNTHETIC] Lighting looks overly staged per brand lead."},
                ],
                [
                    {"role": "reviewer", "action": "override", "reason": "[SYNTHETIC] Real customer office photo is authentic."},
                    {"role": "legal_reviewer", "action": "accept"},
                ],
                [
                    {"role": "reviewer", "action": "accept"},
                    {"role": "admin", "action": "override", "reason": "[SYNTHETIC] Disagreement on R-14 stock aesthetic."},
                ],
                [
                    {"role": "reviewer", "action": "accept"},
                ],
            ],
        }
    )

    # R-16: collides with R-03 + high override rate (50%)
    scenarios.append(
        {
            "label": "R-16-ambiguous",
            "text": "[SYNTHETIC] Calibration batch for R-16: Hyperscale multi-region telemetry scale.",
            "signals": [
                {
                    "rule_id": "R-16",
                    "type": "unsupported",
                    "severity": "medium",
                    "confidence": 0.66,
                    "abstained": False,
                    "quote": "Global planetary-scale compliance engine",
                    "explanation": "[SYNTHETIC] Potential scale overstatement colliding with R-03 quantitative rule.",
                    "matched_sources": ["R-16", "R-03"],
                }
                for _ in range(4)
            ],
            "decision_plan": [
                [{"role": "legal_reviewer", "action": "override", "reason": "[SYNTHETIC] Verified F-112 customer scale satisfies R-03 despite R-16 overlap."}],
                [{"role": "legal_reviewer", "action": "dispute", "reason": "[SYNTHETIC] R-16 guidance conflicts with R-03 quantitative standard."}],
                [{"role": "legal_reviewer", "action": "accept"}],
                [{"role": "legal_reviewer", "action": "accept"}],
            ],
        }
    )

    return scenarios


def run_synthetic_history(
    client: Any,
    password: str = "password123",
    seed_missing_rules: bool = True,
) -> Dict[str, Any]:
    """Drive FastAPI endpoints to generate labelled synthetic decision history."""
    role_headers = {
        "admin": _login(client, "admin@meridian.flow", password),
        "creator": _login(client, "creator@meridian.flow", password),
        "reviewer": _login(client, "reviewer@meridian.flow", password),
        "legal_reviewer": _login(client, "legal@meridian.flow", password),
    }

    if seed_missing_rules:
        _ensure_rules_seeded(client, role_headers["admin"])

    plan = _build_synthetic_plan()
    created_findings = 0
    created_decisions = 0

    for item in plan:
        # 1. Upload synthetic draft through real POST /content endpoint
        upload_resp = client.post(
            "/content",
            data={"title": f"[SYNTHETIC] {item['label']}", "sensitivity": "internal"},
            files={
                "file": (
                    f"{item['label']}.md",
                    io.BytesIO(item["text"].encode("utf-8")),
                    "text/markdown",
                )
            },
            headers=role_headers["creator"],
        )
        if upload_resp.status_code != 201:
            raise RuntimeError(f"POST /content failed: {upload_resp.status_code} {upload_resp.text}")
        rev_id = upload_resp.json()["revisions"][0]["id"]

        # 2. Trigger review run through real POST /revisions/{id}/review endpoint
        review_resp = client.post(
            f"/revisions/{rev_id}/review",
            json={"sensitivity": "internal", "synthetic_signals": item["signals"]},
            headers=role_headers["creator"],
        )
        if review_resp.status_code != 202:
            raise RuntimeError(
                f"POST /revisions/{rev_id}/review failed: {review_resp.status_code} {review_resp.text}"
            )

        # 3. Query routed findings via GET /revisions/{id}/findings and verify queue visibility
        findings_resp = client.get(f"/revisions/{rev_id}/findings", headers=role_headers["reviewer"])
        if findings_resp.status_code != 200:
            raise RuntimeError(
                f"GET /revisions/{rev_id}/findings failed: {findings_resp.status_code} {findings_resp.text}"
            )
        findings = findings_resp.json()
        created_findings += len(findings)

        # Also query GET /findings/queue for routing verification (Y-12)
        for q_role in ("reviewer", "legal_reviewer"):
            q_resp = client.get(f"/findings/queue?role={q_role}", headers=role_headers[q_role])
            if q_resp.status_code != 200:
                raise RuntimeError(f"GET /findings/queue failed: {q_resp.status_code}")

        # 4. Submit decisions via real POST /findings/{id}/decision endpoint
        for idx, finding in enumerate(findings):
            decisions_for_finding = (
                item["decision_plan"][idx] if idx < len(item["decision_plan"]) else [{"role": "reviewer", "action": "accept"}]
            )
            for dec in decisions_for_finding:
                hdrs = role_headers[dec["role"]]
                payload: Dict[str, Any] = {"action": dec["action"]}
                if "reason" in dec:
                    payload["reason"] = dec["reason"]
                dec_resp = client.post(
                    f"/findings/{finding['finding_id']}/decision",
                    json=payload,
                    headers=hdrs,
                )
                if dec_resp.status_code not in (200, 201):
                    raise RuntimeError(
                        f"POST /findings/{finding['finding_id']}/decision failed: "
                        f"{dec_resp.status_code} {dec_resp.text}"
                    )
                created_decisions += 1

    radar_resp = client.get("/insights/radar", headers=role_headers["admin"])
    if radar_resp.status_code != 200:
        raise RuntimeError(f"GET /insights/radar failed: {radar_resp.status_code} {radar_resp.text}")

    return {
        "created_findings": created_findings,
        "created_decisions": created_decisions,
        "radar": radar_resp.json(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate synthetic review decisions via real FastAPI endpoints (Y-24)."
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("AXIOM_API_URL", "http://localhost:8000"),
        help="Running FastAPI base URL (default: http://localhost:8000).",
    )
    parser.add_argument(
        "--in-process",
        action="store_true",
        help="Run directly against FastAPI TestClient(app) without an external server.",
    )
    parser.add_argument(
        "--password",
        default="password123",
        help="Password for seeded Meridian Flow accounts.",
    )
    args = parser.parse_args()

    if args.in_process:
        from fastapi.testclient import TestClient
        from api.src.main import app

        with TestClient(app) as client:
            summary = run_synthetic_history(client, password=args.password)
    else:
        with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
            summary = run_synthetic_history(client, password=args.password)

    radar_summary = summary["radar"]["summary"]
    print(
        f"Generated {summary['created_findings']} synthetic findings and "
        f"{summary['created_decisions']} decisions via FastAPI endpoints."
    )
    print(
        f"Ambiguity Radar: flagged={radar_summary['flagged_count']}/{radar_summary['total_rules_evaluated']}, "
        f"seeded_ambiguous={radar_summary['seeded_ambiguous_flagged_count']}/{radar_summary['seeded_ambiguous_total']}, "
        f"false_flags={radar_summary['false_flags']}/{radar_summary['control_rules_evaluated']} "
        f"(rate={radar_summary['false_flag_rate']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

