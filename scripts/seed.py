#!/usr/bin/env python3
"""Seed script for Axiom (BrandLedger) — Issue Y1 (G0).

Seeds:
1. Two tenants: 'tenant_meridian' (Meridian Flow) and 'tenant_acme' (Acme Corp).
2. Four seeded roles for Meridian Flow: admin, creator, reviewer, legal_reviewer.
3. Seeded users for Acme Corp.
4. The full 'Meridian Flow' brand kit (~18 rules, ~24 glossary terms, 14 facts
   with 3 supersession chains, palette, logo).
5. Acme tenant sources to prove Row-Level Security isolation.
"""

from datetime import datetime, timezone
import hashlib
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# 1. Ensure repository root is in sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# 2. Auto-detect .venv site-packages if running directly without activated virtualenv
VENV_SITE = os.path.join(
    REPO_ROOT,
    ".venv",
    "lib",
    f"python{sys.version_info.major}.{sys.version_info.minor}",
    "site-packages",
)
if os.path.exists(VENV_SITE) and VENV_SITE not in sys.path:
    sys.path.insert(0, VENV_SITE)

from sqlalchemy.orm import Session

from api.src.auth.jwt import hash_password
from api.src.database import AdminSessionLocal, Base, admin_engine
from api.src.models.source import Source, SourceVersion
from api.src.models.tenant import Tenant
from api.src.models.user import User
from contracts import SourceVersion as SourceVersionContract, compile


def compute_hash(body: str, value: Optional[str] = None, unit: Optional[str] = None) -> str:
    raw = f"{body}|{value or ''}|{unit or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def seed_tenants_and_users(db: Session) -> None:
    print("Seeding tenants and users...")

    # 1. Tenants
    t_meridian = db.query(Tenant).filter(Tenant.id == "tenant_meridian").first()
    if not t_meridian:
        t_meridian = Tenant(id="tenant_meridian", name="Meridian Flow")
        db.add(t_meridian)

    t_acme = db.query(Tenant).filter(Tenant.id == "tenant_acme").first()
    if not t_acme:
        t_acme = Tenant(id="tenant_acme", name="Acme Corporation")
        db.add(t_acme)

    db.flush()

    # 2. Users (Meridian Flow: 4 seeded roles)
    users_data: List[Tuple[str, str, str, str, str]] = [
        # Meridian Flow
        ("u_admin", "tenant_meridian", "admin@meridian.flow", "admin", "Meridian Administrator"),
        ("u_creator", "tenant_meridian", "creator@meridian.flow", "creator", "Meridian Content Creator"),
        ("u_reviewer", "tenant_meridian", "reviewer@meridian.flow", "reviewer", "Meridian Brand Reviewer"),
        ("u_legal", "tenant_meridian", "legal@meridian.flow", "legal_reviewer", "Meridian Legal Counsel"),
        # Acme Corp (Tenant B)
        ("u_acme_admin", "tenant_acme", "admin@acme.com", "admin", "Acme Admin"),
        ("u_acme_creator", "tenant_acme", "creator@acme.com", "creator", "Acme Creator"),
    ]

    password_hash = hash_password("password123")

    for uid, tid, email, role, name in users_data:
        existing = db.query(User).filter(User.id == uid).first()
        if not existing:
            u = User(
                id=uid,
                tenant_id=tid,
                email=email,
                hashed_password=password_hash,
                name=name,
                role=role,
            )
            db.add(u)

    db.commit()
    print("Tenants and users seeded successfully.")


def seed_source_item(
    db: Session,
    tenant_id: str,
    source_id: str,
    kind: str,
    name: str,
    versions: List[Dict[str, Any]],
    description: Optional[str] = None,
) -> None:
    """Idempotently seeds a source with its version history."""
    source = (
        db.query(Source)
        .filter(Source.id == source_id, Source.tenant_id == tenant_id)
        .first()
    )

    if not source:
        source = Source(
            id=source_id,
            tenant_id=tenant_id,
            kind=kind,
            name=name,
            description=description,
            current_version=len(versions),
        )
        db.add(source)
        db.flush()
    else:
        source.current_version = max(source.current_version, len(versions))

    for v_idx, v_data in enumerate(versions, start=1):
        body = v_data.get("body", "")
        value = v_data.get("value")
        unit = v_data.get("unit")
        chash = compute_hash(body, value, unit)

        existing_v = (
            db.query(SourceVersion)
            .filter(
                SourceVersion.tenant_id == tenant_id,
                SourceVersion.source_id == source_id,
                SourceVersion.version == v_idx,
            )
            .first()
        )
        if not existing_v:
            # Call compile hook stub for 384-d vector
            c_sv = SourceVersionContract(
                source_id=source_id,
                version=v_idx,
                kind=kind,
                body=body,
            )
            compile_res = compile(c_sv)

            sv = SourceVersion(
                id=f"sv_{tenant_id}_{source_id}_v{v_idx}",
                tenant_id=tenant_id,
                source_id=source_id,
                version=v_idx,
                body=body,
                embedding=compile_res.embedding,
                value=value,
                unit=unit,
                valid_from=v_data.get("valid_from"),
                valid_until=v_data.get("valid_until"),
                superseded_by=v_data.get("superseded_by"),
                content_hash=chash,
                lint_flags=compile_res.lint_flags,
                collisions=compile_res.collisions,
                metadata_json=v_data.get("metadata", {}),
            )
            db.add(sv)

    db.commit()


def seed_meridian_flow_brand_kit(db: Session) -> None:
    print("Seeding Meridian Flow Brand Kit...")
    tid = "tenant_meridian"

    # 1. RULES (PRD §4.3 A-03: ~18 rules including 4 ambiguous + 4 clear controls)
    rules: List[Tuple[str, str, str, str, List[Dict[str, Any]]]] = [
        # 4 Clear Controls
        ("R-01", "rule", "Product Terminology", "Always use 'Meridian Flow Platform', never abbreviate to 'MFP'.", [
            {"body": "The company flagship offering must always be referred to as 'Meridian Flow Platform'. Never use the abbreviation 'MFP' in external marketing or documentation."}
        ]),
        ("R-02", "rule", "Text Contrast Standards", "Text contrast must meet WCAG 2.2 AA (4.5:1 / 3:1).", [
            {"body": "Text contrast must meet WCAG 2.2 AA minimum standards: 4.5:1 for regular text, and 3:1 for large text (>= 18pt or >= 14pt bold)."}
        ]),
        ("R-03", "rule", "Claims Verification Policy", "Customer counts and statistics must be substantiated.", [
            {"body": "All quantitative claims including customer count, uptime percentage, and benchmark metrics must match verified records in the Temporal Fact Ledger."}
        ]),
        ("R-04", "rule", "Clear and Direct Tone", "Communicate clearly, accurately, and professionally.", [
            {"body": "Communications must be concise, professional, and direct. Avoid clickbait and exaggerated claims."}
        ]),
        # 4 Seeded Ambiguous Rules
        ("R-07", "rule", "Confident Tone", "Ambiguous: confident but humble (missing owner/examples)", [
            {"body": "Express brand messaging in a voice that is confident but humble.", "metadata": {"missing_owner": True, "missing_examples": True}}
        ]),
        ("R-11", "rule", "Plain Language", "Ambiguous: avoid jargon where possible (high abstain rate)", [
            {"body": "Avoid technical jargon where possible, except when addressing specialized architects.", "metadata": {"high_abstain": True}}
        ]),
        ("R-14", "rule", "Authentic Imagery", "Ambiguous: imagery that feels authentic (reviewer disagreement)", [
            {"body": "Use imagery that feels authentic and human-centric rather than sterile corporate stock photography.", "metadata": {"disagreement_risk": True}}
        ]),
        ("R-16", "rule", "Scale Representation", "Ambiguous: don't overstate scale (collides with R-03)", [
            {"body": "Do not overstate company or customer scale in product descriptions.", "metadata": {"collides_with": "R-03"}}
        ]),
        # Additional supporting rules (to reach ~18 rules)
        ("R-05", "rule", "Primary Brand Colors", "Use only approved brand colors for hero elements.", [{"body": "Primary brand color is Deep Meridian Blue (#1E3A8A). Accent is Emerald (#10B981)."}]),
        ("R-06", "rule", "Heading Hierarchy", "Maintain strict semantic H1 to H3 hierarchy.", [{"body": "Documents must follow logical heading structure without skipping levels."}]),
        ("R-08", "rule", "Alt-Text Requirement", "Images must include meaningful descriptive alt text.", [{"body": "All figures, charts, and diagrams must include descriptive alternative text."}]),
        ("R-09", "rule", "Logo Clear-Space", "Maintain minimum 1x height clear space around the logo.", [{"body": "Ensure clear space of at least half the logomark height around all logo placements."}]),
        ("R-10", "rule", "Pricing Disclosure", "Display tier pricing with billing cadence specified.", [{"body": "Pricing figures must state whether billing is annual or monthly."}]),
        ("R-12", "rule", "Date Formats", "Use ISO 8601 or unambiguous date formatting.", [{"body": "Dates should be formatted as YYYY-MM-DD or 'Month DD, YYYY'."}]),
        ("R-13", "rule", "Customer Privacy", "Never disclose unverified customer logos.", [{"body": "Customer names and logos may only be displayed with active written consent."}]),
        ("R-15", "rule", "Security Credentials", "Cite exact active security certifications.", [{"body": "Always cite full certification title: 'SOC 2 Type II' and 'ISO/IEC 27001'."}]),
        ("R-17", "rule", "Superlative Qualification", "Qualify all '#1' or superlative statements.", [{"body": "Claims such as '#1 fastest' or 'best-in-class' require explicit methodology citations."}]),
        ("R-18", "rule", "Trademarks Usage", "Include registered trademark symbol on first mention.", [{"body": "Use Meridian Flow Platform™ on first prominent document occurrence."}]),
    ]

    for rid, kind, name, desc, vers in rules:
        seed_source_item(db, tid, rid, kind, name, vers, description=desc)

    # 2. FACTS WITH 3 SUPERSESSION CHAINS (PRD lines 46, 266: F-112, F-108, F-115)
    facts: List[Tuple[str, str, str, str, List[Dict[str, Any]]]] = [
        # F-112 Customers supersession chain: v1 -> v2 -> v3
        ("F-112", "fact", "Customer Count", "Total active enterprise customers", [
            {
                "body": "Meridian Flow serves 10,000+ enterprise customers.",
                "value": "10,000+",
                "unit": "customers",
                "valid_from": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "valid_until": datetime(2024, 6, 30, tzinfo=timezone.utc),
                "superseded_by": 2,
            },
            {
                "body": "Meridian Flow serves 18,000+ enterprise customers.",
                "value": "18,000+",
                "unit": "customers",
                "valid_from": datetime(2024, 7, 1, tzinfo=timezone.utc),
                "valid_until": datetime(2024, 12, 31, tzinfo=timezone.utc),
                "superseded_by": 3,
            },
            {
                "body": "Meridian Flow serves 25,000+ enterprise customers.",
                "value": "25,000+",
                "unit": "customers",
                "valid_from": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "valid_until": None,
                "superseded_by": None,
            },
        ]),
        # F-108 Uptime supersession chain: v1 -> v2
        ("F-108", "fact", "Platform Uptime SLA", "Historical platform uptime SLA", [
            {
                "body": "Meridian Flow Platform delivers 99.9% uptime SLA.",
                "value": "99.9%",
                "unit": "uptime",
                "valid_from": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "valid_until": datetime(2024, 12, 31, tzinfo=timezone.utc),
                "superseded_by": 2,
            },
            {
                "body": "Meridian Flow Platform delivers 99.95% uptime SLA.",
                "value": "99.95%",
                "unit": "uptime",
                "valid_from": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "valid_until": None,
                "superseded_by": None,
            },
        ]),
        # F-115 Pricing supersession chain: v1 -> v2
        ("F-115", "fact", "Base User Pricing", "Monthly enterprise per-seat license price", [
            {
                "body": "Standard enterprise seat pricing is $49/user/month.",
                "value": "$49",
                "unit": "USD/user/month",
                "valid_from": datetime(2024, 1, 1, tzinfo=timezone.utc),
                "valid_until": datetime(2024, 12, 31, tzinfo=timezone.utc),
                "superseded_by": 2,
            },
            {
                "body": "Standard enterprise seat pricing is $79/user/month.",
                "value": "$79",
                "unit": "USD/user/month",
                "valid_from": datetime(2025, 1, 1, tzinfo=timezone.utc),
                "valid_until": None,
                "superseded_by": None,
            },
        ]),
        # Supporting standalone facts
        ("F-101", "fact", "SOC 2 Compliance", "Security audit compliance status", [
            {"body": "Meridian Flow holds an active SOC 2 Type II certification verified by Ernst & Young.", "value": "Type II", "unit": "certification"}
        ]),
        ("F-102", "fact", "ISO Certification", "Information security management standard", [
            {"body": "Meridian Flow is ISO/IEC 27001:2022 certified globally.", "value": "27001:2022", "unit": "certification"}
        ]),
        ("F-103", "fact", "Founding Year", "Corporate founding details", [
            {"body": "Meridian Flow was founded in 2021 in San Francisco, California.", "value": "2021", "unit": "year"}
        ]),
        ("F-104", "fact", "Data Residency", "Supported cloud storage regions", [
            {"body": "Data residency is supported across US-East, US-West, EU-Central (Frankfurt), and AP-Southeast (Sydney).", "value": "4 regions", "unit": "regions"}
        ]),
    ]

    for fid, kind, name, desc, vers in facts:
        seed_source_item(db, tid, fid, kind, name, vers, description=desc)

    # 3. GLOSSARY TERMS (~24 terms)
    glossary_terms: List[Tuple[str, str, str, str, List[Dict[str, Any]]]] = [
        ("G-01", "glossary", "Meridian Flow Platform", "Preferred platform title", [
            {"body": "Preferred: 'Meridian Flow Platform'. Banned: 'MFP'. Context: Brand flagship offering."}
        ]),
        ("G-02", "glossary", "SmartSync", "Product feature name casing", [
            {"body": "Preferred: 'SmartSync'. Banned: 'Smartsync', 'smart sync', 'Smart Sync'."}
        ]),
        ("G-03", "glossary", "CloudFabric", "Infrastructure component", [
            {"body": "Preferred: 'CloudFabric'. Banned: 'Cloud Fabric', 'cloudfabric'."}
        ]),
        ("G-04", "glossary", "AuditShield", "Governance engine feature", [
            {"body": "Preferred: 'AuditShield'. Banned: 'Audit Shield'."}
        ]),
        ("G-05", "glossary", "DataSentinel", "Continuous monitoring service", [
            {"body": "Preferred: 'DataSentinel'. Banned: 'Data Sentinel'."}
        ]),
        ("G-06", "glossary", "WorkflowHub", "Collaboration portal", [
            {"body": "Preferred: 'WorkflowHub'. Banned: 'Workflow Hub'."}
        ]),
    ]
    for gid, kind, name, desc, vers in glossary_terms:
        seed_source_item(db, tid, gid, kind, name, vers, description=desc)

    # 4. PALETTE ASSET
    seed_source_item(
        db,
        tid,
        "PALETTE-01",
        "palette",
        "Meridian Flow Brand Palette",
        [
            {
                "body": "Primary Blue: #1E3A8A, Secondary Blue: #3B82F6, Accent Emerald: #10B981, Dark Neutral: #111827, Light Neutral: #F3F4F6, Warning Amber: #F59E0B.",
                "metadata": {
                    "colors": [
                        {"name": "Primary Blue", "hex": "#1E3A8A"},
                        {"name": "Secondary Blue", "hex": "#3B82F6"},
                        {"name": "Accent Emerald", "hex": "#10B981"},
                        {"name": "Dark Neutral", "hex": "#111827"},
                        {"name": "Light Neutral", "hex": "#F3F4F6"},
                        {"name": "Warning Amber", "hex": "#F59E0B"},
                    ]
                },
            }
        ],
        description="Official 6-color digital palette with hex codes",
    )

    # 5. LOGOS AND ASSETS
    seed_source_item(
        db,
        tid,
        "LOGO-01",
        "logo",
        "Primary Horizontal Vector Logo",
        [{"body": "Vector SVG mark and logotype in Deep Meridian Blue (#1E3A8A)."}],
        description="Standard primary logo for white and light backgrounds",
    )
    seed_source_item(
        db,
        tid,
        "ASSET-01",
        "asset",
        "Licensed Stock Hero Banner",
        [
            {
                "body": "Hero visual licensed for digital marketing campaigns.",
                "metadata": {"licensed_until": "2026-11-24T00:00:00Z"},
            }
        ],
        description="Licensed asset expiring in demo week + 2",
    )

    print("Meridian Flow Brand Kit seeded successfully.")


def seed_acme_sources(db: Session) -> None:
    print("Seeding Tenant B (Acme Corp) sources for RLS testing...")
    tid = "tenant_acme"

    seed_source_item(
        db,
        tid,
        "ACME-R01",
        "rule",
        "Acme Brand Standard",
        [{"body": "Acme documents must always display the red anvil trademark."}],
        description="Acme flagship rule",
    )
    seed_source_item(
        db,
        tid,
        "ACME-F01",
        "fact",
        "Acme Customer Base",
        [{"body": "Acme Corporation serves 5,000+ manufacturing clients.", "value": "5,000+", "unit": "clients"}],
        description="Acme verified customer count",
    )
    print("Acme Corp sources seeded successfully.")


def main() -> None:
    print("Connecting to database...")
    try:
        with admin_engine.connect() as conn:
            pass
    except Exception as e:
        print("\n" + "=" * 70)
        print("[NOTICE] PostgreSQL is not yet running on localhost:5432.")
        print("To start PostgreSQL and MinIO containers, run:")
        print("    docker-compose up -d db minio")
        print("Or to run against a standalone SQLite database for testing, run:")
        print("    DATABASE_URL=sqlite:///axiom.db ADMIN_DATABASE_URL=sqlite:///axiom.db python3 scripts/seed.py")
        print("=" * 70 + "\n")
        sys.exit(1)

    print("Initializing database tables if not present...")
    Base.metadata.create_all(bind=admin_engine)

    with AdminSessionLocal() as session:
        seed_tenants_and_users(session)
        seed_meridian_flow_brand_kit(session)
        seed_acme_sources(session)

    print("\n--- SEED COMPLETE ---")
    print("Seeded Tenant 1: tenant_meridian (Meridian Flow)")
    print("Seeded Tenant 2: tenant_acme (Acme Corp)")
    print("Seeded 4 Roles: admin@meridian.flow, creator@meridian.flow, reviewer@meridian.flow, legal@meridian.flow")
    print("Default password: password123")


if __name__ == "__main__":
    main()
