"""Meridian Flow brand kit fixture data (A-03, Issue #2).

Meridian Flow is a fictional B2B SaaS company used for seeded testing.

Design rules for the seeded content:
  - R-01..R-04: 4 clear control rules (used to measure false-flag rate, I3).
  - R-05..R-06, R-08..R-10, R-12..R-13, R-17..R-18: Normal rules.
  - R-07: ambiguous — "confident but humble" (no owner, no examples → lint flag).
  - R-11: ambiguous — "avoid jargon where possible" (expected high abstain rate).
  - R-14: ambiguous — "imagery that feels authentic" (expected reviewer disagreement).
  - R-16: ambiguous — "don't overstate scale" (collides with R-03 claims policy).

Fact supersession chains (Temporal Fact Ledger, I1):
  - F-112: customers  v1 10,000+ → v2 18,000+ → v3 25,000+
  - F-108: uptime     v1 99.9%   → v2 99.95%
  - F-115: pricing    v1         → v2

Palette: 6 colours.
Logos:   2 (primary + monochrome).
Licensed asset: stock photo expiring demo week + 2 (2026-11-24).
"""

from __future__ import annotations

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
# Rules — 18 total (4 clear controls + 4 seeded ambiguous + 10 standard)
# ---------------------------------------------------------------------------

RULES: list[BrandRule] = [
    # --- Clear control rules R-01..R-04 ----------------------------------------
    BrandRule(
        rule_id="R-01",
        kind=RuleKind.control,
        title="Use only approved product names",
        description=(
            "Always write 'Meridian Flow' in full. Never abbreviate to 'MFP', "
            "'MF', or any other short form. The full name must appear exactly as "
            "shown in the glossary on first mention per document."
        ),
        owner="brand@meridianflow.io",
        good_examples=[
            "Meridian Flow simplifies enterprise compliance workflows.",
            "Teams using Meridian Flow report faster audit cycles.",
        ],
        bad_examples=[
            "MFP handles all your compliance needs.",
            "The MF platform integrates with Salesforce.",
        ],
    ),
    BrandRule(
        rule_id="R-02",
        kind=RuleKind.control,
        title="Cite only approved, versioned facts",
        description=(
            "Any numerical claim about Meridian Flow (customers, uptime, pricing) "
            "must match the active version in the Temporal Fact Ledger. "
            "Superseded figures must not appear in public-facing copy."
        ),
        owner="legal@meridianflow.io",
        good_examples=[
            "Over 25,000+ customers trust Meridian Flow (as of Q1 2026).",
            "Meridian Flow guarantees 99.95% uptime.",
        ],
        bad_examples=[
            "More than 10,000 customers use Meridian Flow.",
            "We offer 99.9% uptime — industry-leading reliability.",
        ],
    ),
    BrandRule(
        rule_id="R-03",
        kind=RuleKind.control,
        title="Substantiate all comparative or superlative claims",
        description=(
            "Claims such as '#1', 'best', 'fastest', 'most secure' must be "
            "supported by a cited, verifiable source stored in the Knowledge Base. "
            "Unsubstantiated superlatives must be qualified or removed."
        ),
        owner="legal@meridianflow.io",
        good_examples=[
            "Meridian Flow ranked #1 in the 2025 TrustRadius Compliance category "
            "(source: TrustRadius Report, Nov 2025).",
        ],
        bad_examples=[
            "Meridian Flow is the #1 compliance platform.",
            "The industry's fastest audit engine — guaranteed.",
        ],
    ),
    BrandRule(
        rule_id="R-04",
        kind=RuleKind.control,
        title="No unapproved external logos or brand marks",
        description=(
            "Only use third-party logos that have written permission on file. "
            "Every logo must be the most recent version from the licensor's "
            "brand portal. Expired or unofficial marks must be removed."
        ),
        owner="design@meridianflow.io",
        good_examples=[
            "Salesforce logo used under approved partner agreement (file: PA-2025-003).",
        ],
        bad_examples=[
            "Using a screenshot crop of the Salesforce logo downloaded from Google Images.",
        ],
    ),
    # --- Standard rules R-05..R-06 ---------------------------------------------
    BrandRule(
        rule_id="R-05",
        kind=RuleKind.control,
        title="Maintain brand voice: professional, clear, and human",
        description=(
            "Copy must be written in second person ('you / your team'), active voice, "
            "and plain language targeting a reading level of Grade 10 or below "
            "(Flesch-Kincaid). Avoid passive voice except in legal disclaimers."
        ),
        owner="content@meridianflow.io",
        good_examples=[
            "You can automate your compliance reviews in minutes.",
            "Your team gets instant visibility into policy gaps.",
        ],
        bad_examples=[
            "Compliance reviews are automatically conducted by the system.",
            "It has been determined that policy gaps exist.",
        ],
    ),
    BrandRule(
        rule_id="R-06",
        kind=RuleKind.control,
        title="Use sentence case for headings",
        description=(
            "All headings and subheadings use sentence case: only the first word "
            "and proper nouns are capitalised. Title Case is not permitted outside "
            "of product names and official report titles."
        ),
        owner="content@meridianflow.io",
        good_examples=["How Meridian Flow automates audit trails"],
        bad_examples=["How Meridian Flow Automates Audit Trails"],
    ),
    # --- Ambiguous rule R-07 (no owner, no examples — lint flag) ---------------
    BrandRule(
        rule_id="R-07",
        kind=RuleKind.ambiguous,
        title="Confident but humble",
        description=(
            "Copy should convey confidence in the product's capabilities while "
            "avoiding arrogance or over-promise. Strike a tone that is assured "
            "yet approachable."
        ),
        owner=None,         # Intentionally absent → lint flag: missing_owner
        good_examples=[],   # Intentionally empty → lint flag: missing_examples
        bad_examples=[],
    ),
    # --- Standard rules R-08..R-10 ---------------------------------------------
    BrandRule(
        rule_id="R-08",
        kind=RuleKind.control,
        title="Respect approved colour palette",
        description=(
            "Only the six colours defined in the palette asset may be used in "
            "marketing materials. Use CIEDE2000 ΔE ≤ 2 as the pass threshold. "
            "Off-palette colours require design team approval before publication."
        ),
        owner="design@meridianflow.io",
        good_examples=["Primary button: #1A73E8 (Meridian Blue)."],
        bad_examples=["Using #0055CC instead of #1A73E8 without approval."],
    ),
    BrandRule(
        rule_id="R-09",
        kind=RuleKind.control,
        title="Meet WCAG 2.2 AA contrast minimums",
        description=(
            "All body text must achieve a contrast ratio of 4.5:1 or higher. "
            "Large text (≥18pt or ≥14pt bold) requires 3:1 or higher. "
            "These are hard requirements, not aspirational targets."
        ),
        owner="design@meridianflow.io",
        good_examples=["Body copy: #1C1C1C on #FFFFFF → ratio 19.6:1 (pass)."],
        bad_examples=["Caption: #999999 on #FFFFFF → ratio 2.85:1 (fail AA)."],
    ),
    BrandRule(
        rule_id="R-10",
        kind=RuleKind.control,
        title="All images must have descriptive alt text",
        description=(
            "Every non-decorative image in web and document deliverables must "
            "include meaningful alt text (not 'image' or empty). "
            "Purely decorative images use alt='' per WCAG 2.2 §1.1.1."
        ),
        owner="content@meridianflow.io",
        good_examples=[
            'alt="Meridian Flow dashboard showing real-time audit status for Q4 2025"'
        ],
        bad_examples=['alt="image"', 'alt=""  <!-- on a non-decorative chart -->'],
    ),
    # --- Ambiguous rule R-11 (expected high abstain rate) ----------------------
    BrandRule(
        rule_id="R-11",
        kind=RuleKind.ambiguous,
        title="Avoid jargon where possible",
        description=(
            "Prefer plain-language equivalents over technical acronyms when writing "
            "for a mixed audience. When technical terms are necessary, define them "
            "on first use. 'Where possible' gives reviewers significant latitude."
        ),
        owner="content@meridianflow.io",
        good_examples=[
            "Use 'automated checks' instead of 'CI/CD pipeline validation' in "
            "executive summaries."
        ],
        bad_examples=[
            "Our SOC 2 Type II certified SIEM integration ensures RBAC enforcement."
        ],
    ),
    # --- Standard rules R-12..R-13 ---------------------------------------------
    BrandRule(
        rule_id="R-12",
        kind=RuleKind.control,
        title="Include a clear call to action on every landing page",
        description=(
            "Every web landing page must have exactly one primary CTA button "
            "above the fold. The CTA copy must be action-oriented and no longer "
            "than five words."
        ),
        owner="content@meridianflow.io",
        good_examples=["Start your free trial", "Book a demo today"],
        bad_examples=[
            "Click here to learn more about how Meridian Flow can help your team"
        ],
    ),
    BrandRule(
        rule_id="R-13",
        kind=RuleKind.control,
        title="Customer quotes need explicit written consent",
        description=(
            "Testimonials and customer quotes may only be published after receiving "
            "written consent (email or signed form) from an authorised contact at "
            "the customer organisation. Consent on file must be referenced by ID."
        ),
        owner="legal@meridianflow.io",
        good_examples=[
            '"Meridian Flow cut our audit time by 60%." — Priya Sharma, CTO, Acme Corp '
            "(consent ID: C-2025-114)"
        ],
        bad_examples=[
            '"Meridian Flow is great!" — Anonymous customer (no consent on file)'
        ],
    ),
    # --- Ambiguous rule R-14 (reviewer disagreement) ---------------------------
    BrandRule(
        rule_id="R-14",
        kind=RuleKind.ambiguous,
        title="Imagery that feels authentic",
        description=(
            "Photography and illustrations should feel candid and genuine, "
            "avoiding obviously staged or stock-photo aesthetics. "
            "What 'feels authentic' is intentionally subjective and may require "
            "reviewer judgment."
        ),
        owner="design@meridianflow.io",
        good_examples=["Candid office shots of real Meridian Flow team members."],
        bad_examples=["Generic stock photo of smiling people in suits pointing at laptop."],
    ),
    # --- Standard rule R-15 ----------------------------------------------------
    BrandRule(
        rule_id="R-15",
        kind=RuleKind.control,
        title="Disclose AI-generated content",
        description=(
            "Any content substantially generated by an AI tool must be labelled "
            "'AI-assisted' in a visible note near the content. This applies to "
            "written copy, images, and data summaries."
        ),
        owner="legal@meridianflow.io",
        good_examples=["[AI-assisted] This market summary was drafted with AI support."],
        bad_examples=["Presenting AI-generated copy without any disclosure label."],
    ),
    # --- Ambiguous rule R-16 (collides with R-03 claims policy) ----------------
    BrandRule(
        rule_id="R-16",
        kind=RuleKind.ambiguous,
        title="Don't overstate scale",
        description=(
            "Avoid round numbers that imply precision you don't have. "
            "Use ranges or qualifiers ('over', 'more than') for metrics that "
            "fluctuate. This can conflict with R-03 when a cited figure is "
            "exact but the reviewer perceives it as overstated."
        ),
        owner="content@meridianflow.io",
        good_examples=["Over 25,000 customers — updated quarterly."],
        bad_examples=["Exactly 25,312 customers as of this writing."],
        collides_with="R-03",  # Seeded collision for Radar (I3)
    ),
    # --- Standard rules R-17..R-18 ---------------------------------------------
    BrandRule(
        rule_id="R-17",
        kind=RuleKind.control,
        title="Data privacy claims must be verifiable",
        description=(
            "Statements about data handling, encryption, or compliance certifications "
            "must match the current certification status documented in the Trust Centre. "
            "Claims about certifications lapsed more than 90 days ago must be removed."
        ),
        owner="legal@meridianflow.io",
        good_examples=[
            "Meridian Flow is SOC 2 Type II certified (last audit: July 2025)."
        ],
        bad_examples=[
            "We are fully HIPAA-compliant. (Note: HIPAA BAA process not yet complete.)"
        ],
    ),
    BrandRule(
        rule_id="R-18",
        kind=RuleKind.control,
        title="Use consistent date formats",
        description=(
            "All dates in customer-facing content must use the format "
            "'Month D, YYYY' (e.g., 'March 1, 2026'). "
            "ISO 8601 (YYYY-MM-DD) is acceptable in technical documentation only."
        ),
        owner="content@meridianflow.io",
        good_examples=["Last updated: March 1, 2026"],
        bad_examples=["Last updated: 2026-03-01", "Last updated: 01/03/2026"],
    ),
]

# ---------------------------------------------------------------------------
# Glossary — 24 terms
# ---------------------------------------------------------------------------

GLOSSARY: list[GlossaryTerm] = [
    GlossaryTerm(
        term_id="G-01",
        preferred="Meridian Flow",
        banned=["MFP", "MF", "meridianflow", "Meridianflow"],
        notes="Full product name. Never abbreviated in customer-facing copy.",
    ),
    GlossaryTerm(
        term_id="G-02",
        preferred="Meridian Flow Platform",
        banned=["the platform", "MFP"],
        notes="Use when referring specifically to the SaaS offering, not the brand.",
    ),
    GlossaryTerm(
        term_id="G-03",
        preferred="compliance workflow",
        banned=["compliance process", "audit flow"],
        notes="Preferred term for describing what customers run inside Meridian Flow.",
    ),
    GlossaryTerm(
        term_id="G-04",
        preferred="brand governance",
        banned=["brand management", "brand control"],
        notes="Meridian Flow's core value proposition phrase.",
    ),
    GlossaryTerm(
        term_id="G-05",
        preferred="audit trail",
        banned=["audit log", "activity log"],
        notes="Preferred term for the immutable record of approvals and changes.",
    ),
    GlossaryTerm(
        term_id="G-06",
        preferred="knowledge base",
        banned=["KB", "guideline database", "rules DB"],
        notes="Refers to the ingested guidelines stored by the platform.",
    ),
    GlossaryTerm(
        term_id="G-07",
        preferred="finding",
        banned=["issue", "flag", "alert", "violation"],
        notes="The standard term for a detected brand guideline deviation.",
    ),
    GlossaryTerm(
        term_id="G-08",
        preferred="suggested fix",
        banned=["auto-correction", "autocorrect", "recommendation"],
        notes="The proposed edit generated for a finding.",
    ),
    GlossaryTerm(
        term_id="G-09",
        preferred="pre-check",
        banned=["automated review", "auto-review", "scan"],
        notes="The automated review pass run before human review.",
    ),
    GlossaryTerm(
        term_id="G-10",
        preferred="Temporal Fact Ledger",
        banned=["fact database", "facts DB", "TFL"],
        notes="Proper name of the versioned fact store; always capitalised.",
    ),
    GlossaryTerm(
        term_id="G-11",
        preferred="Citation Verifier",
        banned=["fact-checker", "verifier", "citation checker"],
        notes="Proper name of the anti-hallucination node; always capitalised.",
    ),
    GlossaryTerm(
        term_id="G-12",
        preferred="Intent Card",
        banned=["intent brief", "content brief", "purpose card"],
        notes="Creator-editable brief used to constrain fix generation.",
    ),
    GlossaryTerm(
        term_id="G-13",
        preferred="Ambiguity Radar",
        banned=["rule radar", "ambiguity monitor"],
        notes="Proper name of the rule-quality signal dashboard.",
    ),
    GlossaryTerm(
        term_id="G-14",
        preferred="hash-bound approval",
        banned=["locked approval", "content-locked approval"],
        notes="Approval tied to a SHA-256 content hash.",
    ),
    GlossaryTerm(
        term_id="G-15",
        preferred="sensitivity label",
        banned=["classification", "data class", "data label"],
        notes="One of: Public, Internal, Restricted.",
    ),
    GlossaryTerm(
        term_id="G-16",
        preferred="bounding box",
        banned=["highlight box", "selection box", "bbox"],
        notes="The normalised [page, x0, y0, x1, y1] overlay region.",
    ),
    GlossaryTerm(
        term_id="G-17",
        preferred="route to",
        banned=["escalate to", "assign to", "send to"],
        notes="Directing a finding to a reviewer role queue.",
    ),
    GlossaryTerm(
        term_id="G-18",
        preferred="Meridian Blue",
        banned=["brand blue", "primary blue"],
        notes="Named palette colour #1A73E8.",
    ),
    GlossaryTerm(
        term_id="G-19",
        preferred="Meridian Night",
        banned=["brand dark", "dark navy"],
        notes="Named palette colour #0D2B4E.",
    ),
    GlossaryTerm(
        term_id="G-20",
        preferred="Meridian Slate",
        banned=["brand grey", "text grey"],
        notes="Named palette colour #5F6368.",
    ),
    GlossaryTerm(
        term_id="G-21",
        preferred="usage ledger",
        banned=["token log", "cost log", "LLM log"],
        notes="The per-run disclosure and telemetry record.",
    ),
    GlossaryTerm(
        term_id="G-22",
        preferred="Needs judgment",
        banned=["needs review", "uncertain", "maybe"],
        notes="The finding status for ambiguous rules that require human review.",
    ),
    GlossaryTerm(
        term_id="G-23",
        preferred="content unit",
        banned=["text block", "paragraph block", "chunk"],
        notes="A parsed segment of a revision document.",
    ),
    GlossaryTerm(
        term_id="G-24",
        preferred="revision",
        banned=["draft", "version", "document version"],
        notes="A specific submitted version of a content document for review.",
    ),
]

# ---------------------------------------------------------------------------
# Facts — 14 total with 3 supersession chains (F-112, F-108, F-115)
# ---------------------------------------------------------------------------

FACTS: list[BrandFact] = [
    # F-112: customers — 3-step chain (v1→v2→v3)
    BrandFact(
        fact_id="F-112",
        subject="customers",
        metric="count",
        versions=[
            FactVersion(
                version=1,
                value="10,000+",
                unit="customers",
                valid_from=date(2024, 1, 1),
                valid_until=date(2024, 12, 31),
                superseded_by=2,
            ),
            FactVersion(
                version=2,
                value="18,000+",
                unit="customers",
                valid_from=date(2025, 1, 1),
                valid_until=date(2025, 12, 31),
                superseded_by=3,
            ),
            FactVersion(
                version=3,
                value="25,000+",
                unit="customers",
                valid_from=date(2026, 1, 1),
                valid_until=None,       # Active version
                superseded_by=None,
            ),
        ],
    ),
    # F-108: uptime — 2-step chain (v1→v2)
    BrandFact(
        fact_id="F-108",
        subject="uptime",
        metric="percentage",
        versions=[
            FactVersion(
                version=1,
                value="99.9%",
                unit="percent",
                valid_from=date(2024, 1, 1),
                valid_until=date(2025, 5, 31),
                superseded_by=2,
            ),
            FactVersion(
                version=2,
                value="99.95%",
                unit="percent",
                valid_from=date(2025, 6, 1),
                valid_until=None,       # Active version
                superseded_by=None,
            ),
        ],
    ),
    # F-115: pricing tier — 2-step chain (v1→v2)
    BrandFact(
        fact_id="F-115",
        subject="pricing",
        metric="tier_description",
        versions=[
            FactVersion(
                version=1,
                value="Starter $49/month · Growth $149/month · Enterprise custom",
                unit="USD/month",
                valid_from=date(2024, 1, 1),
                valid_until=date(2025, 9, 30),
                superseded_by=2,
            ),
            FactVersion(
                version=2,
                value="Starter $59/month · Growth $179/month · Enterprise custom",
                unit="USD/month",
                valid_from=date(2025, 10, 1),
                valid_until=None,       # Active version
                superseded_by=None,
            ),
        ],
    ),
    # F-101: founding year (single version, no supersession)
    BrandFact(
        fact_id="F-101",
        subject="founding",
        metric="year",
        versions=[
            FactVersion(
                version=1,
                value="2021",
                unit="year",
                valid_from=date(2021, 6, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-102: employees
    BrandFact(
        fact_id="F-102",
        subject="employees",
        metric="count",
        versions=[
            FactVersion(
                version=1,
                value="200+",
                unit="employees",
                valid_from=date(2024, 1, 1),
                valid_until=date(2025, 3, 31),
                superseded_by=2,
            ),
            FactVersion(
                version=2,
                value="350+",
                unit="employees",
                valid_from=date(2025, 4, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-103: countries served
    BrandFact(
        fact_id="F-103",
        subject="countries_served",
        metric="count",
        versions=[
            FactVersion(
                version=1,
                value="40+",
                unit="countries",
                valid_from=date(2024, 1, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-104: integrations
    BrandFact(
        fact_id="F-104",
        subject="integrations",
        metric="count",
        versions=[
            FactVersion(
                version=1,
                value="80+",
                unit="integrations",
                valid_from=date(2024, 6, 1),
                valid_until=date(2025, 6, 30),
                superseded_by=2,
            ),
            FactVersion(
                version=2,
                value="120+",
                unit="integrations",
                valid_from=date(2025, 7, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-105: average audit time saved
    BrandFact(
        fact_id="F-105",
        subject="audit_time_saved",
        metric="percentage",
        versions=[
            FactVersion(
                version=1,
                value="60%",
                unit="percent",
                valid_from=date(2024, 1, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-106: NPS score
    BrandFact(
        fact_id="F-106",
        subject="nps_score",
        metric="score",
        versions=[
            FactVersion(
                version=1,
                value="72",
                unit="NPS",
                valid_from=date(2025, 1, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-107: data retention period
    BrandFact(
        fact_id="F-107",
        subject="data_retention",
        metric="duration",
        versions=[
            FactVersion(
                version=1,
                value="7 years",
                unit="years",
                valid_from=date(2024, 1, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-109: SOC 2 audit date
    BrandFact(
        fact_id="F-109",
        subject="soc2_audit",
        metric="last_audit_date",
        versions=[
            FactVersion(
                version=1,
                value="July 2025",
                unit="month-year",
                valid_from=date(2025, 7, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-110: trial period
    BrandFact(
        fact_id="F-110",
        subject="free_trial",
        metric="duration_days",
        versions=[
            FactVersion(
                version=1,
                value="14 days",
                unit="days",
                valid_from=date(2024, 1, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-111: TrustRadius rank (supports R-03)
    BrandFact(
        fact_id="F-111",
        subject="trustradius_rank",
        metric="category_rank",
        versions=[
            FactVersion(
                version=1,
                value="#1 in Compliance Management",
                unit="rank",
                valid_from=date(2025, 11, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
    # F-113: implementation time
    BrandFact(
        fact_id="F-113",
        subject="implementation_time",
        metric="duration",
        versions=[
            FactVersion(
                version=1,
                value="under 2 weeks",
                unit="weeks",
                valid_from=date(2024, 1, 1),
                valid_until=None,
                superseded_by=None,
            ),
        ],
    ),
]

# ---------------------------------------------------------------------------
# Palette — 6 approved colours
# ---------------------------------------------------------------------------

PALETTE: list[PaletteColor] = [
    PaletteColor(name="Meridian Blue", hex="#1A73E8", usage="Primary CTA, links, highlights"),
    PaletteColor(name="Meridian Night", hex="#0D2B4E", usage="Headers, navigation background"),
    PaletteColor(name="Meridian Slate", hex="#5F6368", usage="Body text, secondary labels"),
    PaletteColor(name="Meridian Cloud", hex="#F1F3F4", usage="Page background, card surface"),
    PaletteColor(name="Meridian Coral", hex="#E84235", usage="Error states, critical alerts only"),
    PaletteColor(name="Meridian Sage", hex="#34A853", usage="Success states, positive indicators"),
]

# ---------------------------------------------------------------------------
# Logos — 2 assets
# ---------------------------------------------------------------------------

LOGOS: list[LogoAsset] = [
    LogoAsset(
        asset_id="L-01",
        name="Meridian Flow primary logo",
        path="brand_kit/assets/logo_primary.svg",
        formats=["svg", "png"],
    ),
    LogoAsset(
        asset_id="L-02",
        name="Meridian Flow monochrome logo",
        path="brand_kit/assets/logo_mono.svg",
        formats=["svg", "png"],
    ),
]

# ---------------------------------------------------------------------------
# Licensed assets — 1 asset, expiring demo week + 2 (2026-11-24)
# ---------------------------------------------------------------------------

LICENSED_ASSETS: list[LicensedAsset] = [
    LicensedAsset(
        asset_id="LA-01",
        name="Diverse team collaboration stock photo",
        path="brand_kit/assets/stock_team_collab.jpg",
        license="Shutterstock Standard License #SS-2024-887234",
        expires=date(2026, 11, 24),  # Demo week + 2 days
    ),
]

# ---------------------------------------------------------------------------
# Top-level brand kit object
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

