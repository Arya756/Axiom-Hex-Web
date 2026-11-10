"""Meridian Flow brand kit fixture data (A-03).

This module exposes `MERIDIAN_FLOW_KIT` — the complete brand kit used as:
  - Import payload for POST /import/brand-kit
  - Seed data loaded by Yash's seed script (Issue #3, Y-03)
  - Ground truth for the eval harness (Issue #13, A-17)

Fact supersession chains (PRD §4.3 A-03):
  F-112 customers:  v1=10,000+ → v2=18,000+ → v3=25,000+
  F-108 uptime:     v1=99.9%   → v2=99.95%
  F-115 pricing:    v1 (old)   → v2 (current)
"""

from datetime import date

from brand_kit.models import (
    BrandFact,
    BrandKit,
    BrandRule,
    FactVersion,
    GlossaryTerm,
    LicensedAsset,
    LogoAsset,
    PaletteColor,
    RuleKind,
)

# ---------------------------------------------------------------------------
# Rules — 4 clear controls (R-01..R-04) + 10 normal + 4 seeded ambiguous
# ---------------------------------------------------------------------------

RULES: list[BrandRule] = [
    # --- Clear control rules (R-01..R-04) ---
    BrandRule(
        rule_id="R-01",
        kind=RuleKind.control,
        title="Use the full product name on first reference",
        description=(
            "Always use 'Meridian Flow' (never 'MF' or 'MFP') on the first "
            "mention in any external document."
        ),
        owner="brand@meridianflow.io",
        good_examples=["Meridian Flow helps teams automate brand governance."],
        bad_examples=["MFP helps teams automate brand governance."],
    ),
    BrandRule(
        rule_id="R-02",
        kind=RuleKind.control,
        title="Use only approved palette colours",
        description=(
            "All text and graphic elements must use colours from the approved "
            "6-colour palette. Off-palette colours require Brand Ops approval."
        ),
        owner="brand@meridianflow.io",
        good_examples=["Headline in #1A3C5E (Deep Navy)."],
        bad_examples=["Headline in #FF0000 (unapproved red)."],
    ),
    BrandRule(
        rule_id="R-03",
        kind=RuleKind.control,
        title="All numerical claims must cite an approved fact",
        description=(
            "Every statistic, metric, or percentage must resolve to an active "
            "fact version in the Knowledge Base. Superseded facts trigger an "
            "Outdated finding; unresolvable claims trigger Unsupported."
        ),
        owner="legal@meridianflow.io",
        good_examples=["Over 25,000+ customers trust Meridian Flow (F-112 v3)."],
        bad_examples=["Millions of customers trust Meridian Flow."],
    ),
    BrandRule(
        rule_id="R-04",
        kind=RuleKind.control,
        title="No unapproved superlatives",
        description=(
            "Absolute claims such as '#1', 'best', 'fastest', or 'only' require "
            "explicit, verifiable substantiation tied to an approved fact."
        ),
        owner="legal@meridianflow.io",
        good_examples=["Meridian Flow ranked #1 in G2's 2025 Brand Governance report (F-120 v1)."],
        bad_examples=["Meridian Flow is the #1 brand governance platform."],
    ),

    # --- Additional normal rules (R-05, R-06, R-08..R-10, R-12, R-13, R-15, R-17, R-18) ---
    BrandRule(
        rule_id="R-05",
        kind=RuleKind.control,
        title="Logo clear-space: 2× the 'M' cap-height on all sides",
        description=(
            "No other elements may encroach within the defined clear-space "
            "around the Meridian Flow wordmark."
        ),
        owner="brand@meridianflow.io",
        good_examples=["Logo centred with generous white space on the cover page."],
        bad_examples=["Tagline placed directly under the logo, touching the letterform."],
    ),
    BrandRule(
        rule_id="R-06",
        kind=RuleKind.control,
        title="Use sentence case for headings",
        description="All headings use sentence case, not title case or all-caps.",
        owner="brand@meridianflow.io",
        good_examples=["Getting started with brand governance"],
        bad_examples=["Getting Started With Brand Governance"],
    ),
    BrandRule(
        rule_id="R-08",
        kind=RuleKind.control,
        title="Use active voice in product descriptions",
        description="Prefer active-voice constructions to keep copy direct and energetic.",
        owner="content@meridianflow.io",
        good_examples=["Meridian Flow automates your review workflow."],
        bad_examples=["Your review workflow is automated by Meridian Flow."],
    ),
    BrandRule(
        rule_id="R-09",
        kind=RuleKind.control,
        title="Alt text required for all informational images",
        description=(
            "Every image that conveys meaning must have descriptive alt text. "
            "Decorative images use an empty alt attribute."
        ),
        owner="accessibility@meridianflow.io",
        good_examples=['<img src="dashboard.png" alt="Meridian Flow analytics dashboard">'],
        bad_examples=['<img src="dashboard.png">'],
    ),
    BrandRule(
        rule_id="R-10",
        kind=RuleKind.control,
        title="Minimum text contrast ratio 4.5:1 (WCAG AA)",
        description=(
            "Body text must achieve at least 4.5:1 contrast against its background. "
            "Large text (≥18 pt or ≥14 pt bold) requires 3:1."
        ),
        owner="accessibility@meridianflow.io",
        good_examples=["Dark-navy (#1A3C5E) text on white (#FFFFFF) → 12.6:1."],
        bad_examples=["Light-grey (#999999) caption on white (#FFFFFF) → 2.85:1."],
    ),
    BrandRule(
        rule_id="R-12",
        kind=RuleKind.control,
        title="Cite version and effective date for every fact",
        description=(
            "When referencing a versioned fact in external content, include "
            "the fact ID and effective date in a footnote or tooltip."
        ),
        owner="legal@meridianflow.io",
        good_examples=["25,000+ customers as of March 2025 (F-112 v3)."],
        bad_examples=["25,000+ customers."],
    ),
    BrandRule(
        rule_id="R-13",
        kind=RuleKind.control,
        title="No competitor names without legal review",
        description=(
            "Any copy that names a competitor product or company must be "
            "approved by Legal before publication."
        ),
        owner="legal@meridianflow.io",
        good_examples=["Meridian Flow outperforms industry benchmarks."],
        bad_examples=["Meridian Flow is better than CompetitorX."],
    ),
    BrandRule(
        rule_id="R-15",
        kind=RuleKind.control,
        title="Use the approved tagline verbatim",
        description=(
            "The tagline 'Govern every word.' must appear exactly as approved. "
            "No paraphrasing or partial quotes."
        ),
        owner="brand@meridianflow.io",
        good_examples=["Govern every word."],
        bad_examples=["Govern your words.", "Governing every word."],
    ),
    BrandRule(
        rule_id="R-17",
        kind=RuleKind.control,
        title="Disclose AI-assisted content with an 'Assisted' badge",
        description=(
            "Any finding, fix, or summary generated with LLM assistance must "
            "carry a visible 'Assisted' badge in the UI."
        ),
        owner="engineering@meridianflow.io",
        good_examples=["Finding card shows an 'Assisted' badge when LLM generated."],
        bad_examples=["AI-generated finding presented without attribution."],
    ),
    BrandRule(
        rule_id="R-18",
        kind=RuleKind.control,
        title="Restricted content: zero external calls",
        description=(
            "Documents labelled 'Restricted' must never trigger LLM calls or "
            "any external API. Only deterministic checks are permitted."
        ),
        owner="security@meridianflow.io",
        good_examples=["Restricted run: 0 external calls, $0.00 cost."],
        bad_examples=["Restricted document sent to GPT-4o for tone analysis."],
    ),

    # --- Seeded ambiguous rules (R-07, R-11, R-14, R-16) ---
    BrandRule(
        rule_id="R-07",
        kind=RuleKind.ambiguous,
        title="Confident but humble",
        description=(
            "Copy should convey confidence in the product without coming across "
            "as arrogant or dismissive of customer challenges."
        ),
        # Intentionally no owner, no examples — this triggers lint flags
        owner=None,
        good_examples=[],
        bad_examples=[],
    ),
    BrandRule(
        rule_id="R-11",
        kind=RuleKind.ambiguous,
        title="Avoid jargon where possible",
        description=(
            "Prefer plain language over technical or industry jargon, especially "
            "in top-of-funnel marketing. Where jargon is unavoidable, define it "
            "on first use."
        ),
        # Has examples but boundary is subjective — high abstain rate expected
        owner="content@meridianflow.io",
        good_examples=["Meridian Flow makes brand reviews faster and more consistent."],
        bad_examples=["Leverage our LLM-powered agentic RAG pipeline for brand governance."],
    ),
    BrandRule(
        rule_id="R-14",
        kind=RuleKind.ambiguous,
        title="Imagery that feels authentic",
        description=(
            "Photos and illustrations should feel genuine and relatable, not "
            "stock-photo generic. Staged or overly polished imagery is discouraged."
        ),
        # Reviewer disagreement expected — subjective rule
        owner="brand@meridianflow.io",
        good_examples=["Candid team photo from an actual Meridian Flow offsite."],
        bad_examples=["Generic stock photo of smiling people in a glass office."],
    ),
    BrandRule(
        rule_id="R-16",
        kind=RuleKind.ambiguous,
        title="Don't overstate scale",
        description=(
            "Claims about customer count, geographic reach, or platform scale "
            "must be conservative and verifiable. Rounding up aggressively is "
            "not permitted."
        ),
        # Collides with R-03 (claims policy) — handled by collision detector
        owner="legal@meridianflow.io",
        good_examples=["Over 25,000 customers across 40 countries (F-112 v3, F-117 v1)."],
        bad_examples=["Tens of thousands of global customers."],
        collides_with="R-03",
    ),
]

# ---------------------------------------------------------------------------
# Glossary — ~24 terms (PRD §4.3 A-03)
# ---------------------------------------------------------------------------

GLOSSARY: list[GlossaryTerm] = [
    GlossaryTerm(term_id="G-01", preferred="Meridian Flow", banned=["MFP", "MF", "meridian flow"], notes="Always capitalised; never abbreviated externally."),
    GlossaryTerm(term_id="G-02", preferred="Meridian Flow Platform", banned=["MFP", "the platform"], notes="Use full name or 'Meridian Flow' on subsequent refs."),
    GlossaryTerm(term_id="G-03", preferred="brand governance", banned=["brand policing", "brand enforcement"], notes="Preferred framing."),
    GlossaryTerm(term_id="G-04", preferred="review run", banned=["scan", "audit run", "lint pass"], notes="Consistent with product terminology."),
    GlossaryTerm(term_id="G-05", preferred="finding", banned=["issue", "flag", "violation"], notes="'Finding' is the canonical term for a detected guideline concern."),
    GlossaryTerm(term_id="G-06", preferred="suggested fix", banned=["recommendation", "suggestion"], notes="Aligns with UI copy."),
    GlossaryTerm(term_id="G-07", preferred="Knowledge Base", banned=["knowledge base", "KB", "guideline store"], notes="Always title-cased."),
    GlossaryTerm(term_id="G-08", preferred="Intent Card", banned=["intent card", "intent summary"], notes="Title-cased; auto-extracted on pre-check."),
    GlossaryTerm(term_id="G-09", preferred="sensitivity label", banned=["classification", "data class"], notes="Use 'sensitivity label' not 'classification'."),
    GlossaryTerm(term_id="G-10", preferred="Restricted", banned=["confidential", "secret", "top secret"], notes="One of three sensitivity labels: Public / Internal / Restricted."),
    GlossaryTerm(term_id="G-11", preferred="approved", banned=["signed off", "cleared", "green-lit"], notes="Use 'approved' for the terminal positive revision state."),
    GlossaryTerm(term_id="G-12", preferred="Temporal Fact Ledger", banned=["fact store", "fact database"], notes="Internal system name; use 'Knowledge Base' in external copy."),
    GlossaryTerm(term_id="G-13", preferred="Citation Verifier", banned=["hallucination check", "fact checker"], notes="Internal system name."),
    GlossaryTerm(term_id="G-14", preferred="Ambiguity Radar", banned=["rule health", "rule quality"], notes="Internal feature name."),
    GlossaryTerm(term_id="G-15", preferred="bounding box", banned=["bbox", "box overlay"], notes="In external docs; 'bbox' is acceptable in code/JSON."),
    GlossaryTerm(term_id="G-16", preferred="usage ledger", banned=["cost log", "token log"], notes="UI label for telemetry."),
    GlossaryTerm(term_id="G-17", preferred="revision", banned=["version", "draft version", "document version"], notes="'Revision' refers to a draft submission; 'version' is for KB sources."),
    GlossaryTerm(term_id="G-18", preferred="creator", banned=["author", "submitter", "uploader"], notes="Role name in the product."),
    GlossaryTerm(term_id="G-19", preferred="reviewer", banned=["approver", "checker"], notes="Role name. 'Approver' is a valid informal term but 'reviewer' is canonical."),
    GlossaryTerm(term_id="G-20", preferred="evidence-grounded", banned=["evidence-based", "fact-backed"], notes="Preferred descriptor for findings."),
    GlossaryTerm(term_id="G-21", preferred="Govern every word.", banned=["Govern your words.", "Governing every word."], notes="Approved tagline — must be verbatim."),
    GlossaryTerm(term_id="G-22", preferred="pre-check", banned=["pre-scan", "initial review"], notes="Term for the automated review run triggered on upload."),
    GlossaryTerm(term_id="G-23", preferred="hash-bound approval", banned=["locked approval", "content-locked approval"], notes="Technical term for approval tied to SHA-256 content hash."),
    GlossaryTerm(term_id="G-24", preferred="deterministic checker", banned=["rule-based checker", "regex checker"], notes="Preferred technical descriptor."),
]

# ---------------------------------------------------------------------------
# Facts — ~14 facts with 3 supersession chains (PRD §4.3 A-03)
# ---------------------------------------------------------------------------

FACTS: list[BrandFact] = [
    # F-112: Customer count — 3-version supersession chain
    BrandFact(
        fact_id="F-112",
        subject="customers",
        metric="count",
        versions=[
            FactVersion(version=1, value="10,000+", valid_from=date(2023, 1, 1), valid_until=date(2024, 6, 30), superseded_by=2),
            FactVersion(version=2, value="18,000+", valid_from=date(2024, 7, 1), valid_until=date(2025, 2, 28), superseded_by=3),
            FactVersion(version=3, value="25,000+", valid_from=date(2025, 3, 1)),
        ],
    ),
    # F-108: Uptime SLA — 2-version supersession chain
    BrandFact(
        fact_id="F-108",
        subject="uptime",
        metric="SLA percentage",
        versions=[
            FactVersion(version=1, value="99.9%", unit="percent", valid_from=date(2023, 1, 1), valid_until=date(2024, 12, 31), superseded_by=2),
            FactVersion(version=2, value="99.95%", unit="percent", valid_from=date(2025, 1, 1)),
        ],
    ),
    # F-115: Pricing — 2-version supersession chain
    BrandFact(
        fact_id="F-115",
        subject="pricing",
        metric="starting price",
        versions=[
            FactVersion(version=1, value="$299/month", unit="USD/month", valid_from=date(2023, 1, 1), valid_until=date(2024, 9, 30), superseded_by=2),
            FactVersion(version=2, value="$349/month", unit="USD/month", valid_from=date(2024, 10, 1)),
        ],
    ),
    # Remaining stable facts (single version)
    BrandFact(
        fact_id="F-101",
        subject="founding year",
        metric="year",
        versions=[FactVersion(version=1, value="2021", valid_from=date(2021, 1, 1))],
    ),
    BrandFact(
        fact_id="F-102",
        subject="headquarters",
        metric="location",
        versions=[FactVersion(version=1, value="Bangalore, India", valid_from=date(2021, 1, 1))],
    ),
    BrandFact(
        fact_id="F-103",
        subject="employees",
        metric="count",
        versions=[FactVersion(version=1, value="200+", valid_from=date(2025, 1, 1))],
    ),
    BrandFact(
        fact_id="F-104",
        subject="integrations",
        metric="count",
        versions=[FactVersion(version=1, value="50+", valid_from=date(2024, 6, 1))],
    ),
    BrandFact(
        fact_id="F-105",
        subject="countries served",
        metric="count",
        versions=[FactVersion(version=1, value="40+", valid_from=date(2024, 1, 1))],
    ),
    BrandFact(
        fact_id="F-106",
        subject="data processing regions",
        metric="count",
        versions=[FactVersion(version=1, value="3", valid_from=date(2023, 6, 1))],
    ),
    BrandFact(
        fact_id="F-107",
        subject="review speed",
        metric="time",
        versions=[FactVersion(version=1, value="< 60 seconds", unit="seconds", valid_from=date(2024, 3, 1))],
    ),
    BrandFact(
        fact_id="F-109",
        subject="NPS score",
        metric="score",
        versions=[FactVersion(version=1, value="72", valid_from=date(2025, 1, 1))],
    ),
    BrandFact(
        fact_id="F-110",
        subject="SOC 2 Type II",
        metric="certification status",
        versions=[FactVersion(version=1, value="certified", valid_from=date(2024, 4, 1))],
    ),
    BrandFact(
        fact_id="F-111",
        subject="GDPR compliance",
        metric="compliance status",
        versions=[FactVersion(version=1, value="compliant", valid_from=date(2023, 5, 25))],
    ),
    BrandFact(
        fact_id="F-117",
        subject="countries served",
        metric="count",
        versions=[FactVersion(version=1, value="40", valid_from=date(2024, 1, 1))],
    ),
]

# ---------------------------------------------------------------------------
# Palette — 6 approved colours (PRD §4.3 A-03)
# ---------------------------------------------------------------------------

PALETTE: list[PaletteColor] = [
    PaletteColor(name="Deep Navy",   hex="#1A3C5E", usage="Primary text, headings, backgrounds"),
    PaletteColor(name="Meridian Blue", hex="#1A73E8", usage="CTAs, links, interactive elements"),
    PaletteColor(name="Sky Teal",    hex="#00BCD4", usage="Accent, highlights, charts"),
    PaletteColor(name="Pure White",  hex="#FFFFFF", usage="Backgrounds, negative space"),
    PaletteColor(name="Warm Grey",   hex="#F5F5F5", usage="Card backgrounds, dividers"),
    PaletteColor(name="Slate Grey",  hex="#616161", usage="Secondary text, captions — minimum 4.5:1 on white"),
]

# ---------------------------------------------------------------------------
# Logos
# ---------------------------------------------------------------------------

LOGOS: list[LogoAsset] = [
    LogoAsset(
        asset_id="L-01",
        name="Meridian Flow Wordmark",
        path="assets/logos/meridian-flow-wordmark",
        formats=["svg", "png"],
    ),
    LogoAsset(
        asset_id="L-02",
        name="Meridian Flow Icon (M-mark)",
        path="assets/logos/meridian-flow-icon",
        formats=["svg", "png"],
    ),
]

# ---------------------------------------------------------------------------
# Licensed assets — 1 asset expiring in demo week + 2
# (Demo week assumed to start 2026-11-10; expiry = 2026-11-24)
# ---------------------------------------------------------------------------

LICENSED_ASSETS: list[LicensedAsset] = [
    LicensedAsset(
        asset_id="A-01",
        name="Hero illustration: connected workflows",
        path="assets/licensed/hero-illustration-connected-workflows.png",
        license="Shutterstock Standard License",
        expires=date(2026, 11, 24),  # demo week + 2 weeks
    ),
]

# ---------------------------------------------------------------------------
# Full kit
# ---------------------------------------------------------------------------

MERIDIAN_FLOW_KIT = BrandKit(
    tenant_id="meridian-flow",
    version=1,
    rules=RULES,
    glossary=GLOSSARY,
    facts=FACTS,
    palette=PALETTE,
    logos=LOGOS,
    licensed_assets=LICENSED_ASSETS,
)
