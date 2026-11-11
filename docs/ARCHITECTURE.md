# Axiom System Architecture & Technical Decisions

> **Team:** Hex & Web · **Platform & Governance Lead:** Yashkumar Nimje · **Engine Lead:** Ayush Aryan

---

## 1. High-Level Architecture

```text
[Y] Next.js 14 Workspace (Light Mode Soft-Pastel UI, react-pdf + SVG bbox overlays)
      │ HTTPS + JWT (role claims: admin, creator, reviewer, legal_reviewer)
      ▼
[Y] FastAPI Backend (api/src/)
      ├─ Auth & RBAC + Non-owner DB session (SET LOCAL app.tenant_id RLS)
      ├─ Sources & Versioning (/sources, /sources/{id}/versions -> compile hook T5)
      ├─ Content & Revisions (/content, /revisions/{id}/edit, invalidate on approved edit)
      ├─ Review Orchestrator (POST /revisions/{id}/review -> cache key + BackgroundTasks)
      ├─ State Machine & Approvals (/approve, SoD 403, hash lock 409, legal sign-off)
      ├─ Cryptographic Audit Chain (audit_log + PG append-only triggers + verify script)
      └─ Insights & Radar (GET /insights/radar, GET /impact?source_id=, GET /insights/recurring)
      │
      ▼ Calls Python engine entrypoint via typed /contracts (T1–T9)
[A] Multimodal Compliance & Verification Engine (engine/)
      ├─ Parsers (MD, TXT, PDF PyMuPDF rawdict, DOCX, PNG/JPG Tesseract OCR) -> ContentUnits (T2)
      ├─ LangGraph Parallel Checkers (Terminology, Temporal Fact Ledger + BM25/pgvector RRF,
      │   Visual CIEDE2000, WCAG Accessibility, Tone) -> Sensitivity Router (Restricted = 0 external)
      └─ Citation Verifier Gate (anti-hallucination check) + Intent Card Minimal-Edit Fixes (T3, T9)
      │
      ▼
[Y] PostgreSQL 16 + pgvector (vector(384)) & MinIO / S3 Object Storage
```

---

## 2. Yash's Platform & Governance Architecture (`Y-01`–`Y-27`)

### 2.1 Multi-Tenancy & PostgreSQL Row-Level Security (RLS)
- **Non-owner application role (`axiom_app`):** Schema migrations (`alembic upgrade head`) run under the privileged admin role while API transactions execute under `axiom_app` so Postgres RLS policies cannot be implicitly bypassed by table ownership (`docker/init-db.sh`, `api/alembic/versions/001_initial_schema.py`).
- **Transaction-local scoping:** Every tenant-scoped request invokes `SET LOCAL app.tenant_id = :tenant_id` (`api/src/database.py`), preventing tenant context bleed across pooled SQLAlchemy connections.
- **Verification:** Proven by `tests/test_rls_isolation.py` and `tests/api/test_platform_y6.py::test_rls_isolation_tenant_b_cannot_read_tenant_a_y26` using two seeded tenants (`tenant_meridian` and `tenant_acme`).

### 2.2 Run Caching, Stale Watchdog & In-Process Background Execution
- **No separate broker queue tier:** Review runs execute asynchronously inside FastAPI `BackgroundTasks`, with lifecycle state (`queued`, `running`, `partial`, `done`, `failed`) stored in `review_runs` (`api/src/routers/revisions.py`).
- **Composite cache key:** Re-running unchanged drafts reuses cached findings by hashing `(tenant_id, content_hash, ruleset_version, sensitivity_policy, intent_card_hash)`. Any edit to draft bytes (`content_hash`), superseded brand source (`ruleset_version`), sensitivity policy, or Intent Card invalidates cached results automatically.
- **Stale-run watchdog:** Any `review_run` stuck in `running` past `STALE_RUN_TIMEOUT_SECONDS` (300s) is marked stale/failed cleanly so UI flows never hang indefinitely.

### 2.3 Governance State Machine, Finding Routing & Cryptographic Audit Log
- **Role routing (`Y-12`):** `route_finding_by_type` in `api/src/services/governance.py` assigns claim-type findings (`outdated`, `contradicted`, `unsupported`) to `legal_reviewer` and terminology/tone/visual/accessibility findings to `reviewer`.
- **Approval guards (`Y-11`, `Y-13`):**
  - **Separation of Duties:** Authors approving their own revision receive `403 Forbidden`.
  - **Mandatory Legal Sign-Off:** Standard `reviewer` users receive `403 Forbidden` when any claim-type finding existed on the revision; `legal_reviewer` sign-off is required.
  - **Mandatory Written Justification:** Overriding or disputing a finding without a non-empty `reason` returns `422 Unprocessable Entity`.
  - **Hash-Bound Approval & Invalidation:** Approvals bind strictly to `revision.content_hash` (`409 Conflict` on mismatch) and are retry-idempotent per `(revision_id, approver_id, content_hash)`. Editing an approved revision (`POST /content/{id}/revisions` or `POST /revisions/{id}/edit`) immediately marks the prior revision `invalidated` and creates the new revision with status `Invalidated (New Unapproved Revision)`.
- **Append-only SHA-256 hash chain (`Y-14`):** `audit_log` uses serialized appends computing `SHA-256(prev_hash | tenant_id | entity_type | entity_id | action | canonical_payload | utc_timestamp)`. Alembic migration `002_audit_governance` attaches PostgreSQL `BEFORE UPDATE OR DELETE` trigger (`prevent_audit_log_modification`) and revokes `UPDATE`/`DELETE` from `axiom_app`. Verified offline or in CI via `scripts/verify_audit_chain.py`.
- **Workflow State Deviation Record (PRD §2.1):** Rather than suspending LangGraph threads across human wait states (`interrupt`), workflow state lives exclusively in PostgreSQL tables written by FastAPI endpoints; the engine completes at the Aggregator and returns immutable `ReviewResult` data per contract `T1`.

### 2.4 Workspace UI, Bounding-Box Viewer & Improvement 3 Analytics (`Y-16`–`Y-24`)
- **Light Mode & Soft Pastel Design System:** Exclusive Light Mode palette (`web/tailwind.config.ts`, `web/src/`) using `slate-50` canvas, crisp white cards, and pastel status tones (`indigo`, `rose`, `emerald`, `amber`, `purple`) with explicit loading (`role="status"`), empty, and error (`role="alert"`) states.
- **Evidence-First Receipt Cards & Keyboard Accessibility:** `FindingCard.tsx` displays verified citation receipts *before* explanations, tracked-change diffs (`diff`), explicit `"Assisted"` / `"Assisted Fix"` badges on AI-assisted outputs, and full keyboard navigation (`Tab`, `Enter`/`Space`, `ArrowUp`/`ArrowDown`).
- **Two-Way Document Highlight & Normalized BBox Overlay:** Clicking a card or document span highlights both directions; image/PDF annotations scale normalized `[page, x0, y0, x1, y1]` (`viewBox="0 0 1 1"`) SVG rectangles accurately at any zoom (`T2`).
- **Ambiguity Radar & Impact Analysis (Improvement 3):** `api/src/services/analytics.py` aggregates SQL signals over `rule_stats`, reviewer decision disagreements, abstain/low-confidence rates, and ingest collisions to flag unclear guidelines (`R-07`, `R-11`, `R-14`, `R-16`) while keeping `0` false flags on clear controls (`R-01`–`R-04`). `GET /impact?source_id=` surfaces draft and in-review items referencing a modified source, including currently passing `Supported` claims tracked in `ReviewRun.matched_sources`.

---

## 3. Multimodal Engine Notes (Summary of Ayush's Components `A-01`–`A-19`)

*(Engine internals reside in `engine/` and `brand_kit/`, integrated behind `contracts/` T1–T9; see `docs/EVAL.md` / `tests/test_issue*.py` for engine evaluation details.)*
- **Parsers (`engine/parsers.py`):** Extract Markdown, text, PyMuPDF character boxes/color/font size, DOCX runs, and Tesseract 5 OCR word boxes into normalized `ContentUnit` coordinates (`T2`).
- **Hybrid Retrieval & Temporal Fact Ledger (`engine/retrieval.py`, `engine/fact_ledger.py`):** Combines local `BAAI/bge-small-en-v1.5` (`384-d`) embeddings in `pgvector` with `rank_bm25` fused via Reciprocal Rank Fusion (`k=60`) and supersession-chain classification (`Supported`, `Outdated`, `Contradicted`, `Unsupported`).
- **Visual & Accessibility Checkers (`engine/accessibility.py`):** Computes CIEDE2000 palette distance (`scikit-image`) and WCAG 2.2 AA contrast ratios (`4.5:1` / `3:1`).
- **Citation Verifier & Security (`engine/verifier.py`, `engine/llm_client.py`):** Drops unverified citations before rendering receipts; enforces `<untrusted_document_span>` XML delimiters, `temperature=0`, and hard blocks on `Restricted` sensitivity.

