# Axiom (BrandLedger) — Round 2

> **Team:** Hex & Web · **Leads:** Yashkumar Nimje (Platform, Workflow, Governance & UI) & Ayush Aryan (Multimodal Compliance Engine)

Axiom is a multimodal brand governance and claim-verification workspace that audits enterprise marketing drafts (Markdown, Text, PDF, DOCX, PNG/JPG) against versioned guidelines, maintains evidence-first receipts verified by an anti-hallucination Citation Verifier, enforces role-routed approval guards and SHA-256 hash-chained audit logs, and surfaces guideline ambiguity and rule-change impact.

---

## Deployed Links

| Environment | URL | Status |
|---|---|---|
| Web Workspace (Next.js) | `[DEPLOYED_WEB_URL]` *(e.g. `https://axiom-hex-web.example.com`)* | Update on deployment |
| FastAPI Backend & Swagger | `[DEPLOYED_API_URL]/docs` | Update on deployment |
| Health Check | `[DEPLOYED_API_URL]/health` | Expects `{"status": "healthy"}` |

---

## Seeded Judge & Demo Accounts

All seeded demo accounts use the same local demo password: **`password123`** (seeded idempotently by [`scripts/seed.py`](scripts/seed.py)).

### Primary Tenant: Meridian Flow (`tenant_meridian`)

| Role | Email | Password | Capabilities |
|---|---|---|---|
| **Admin** (`admin`) | `admin@meridian.flow` | `password123` | Ingest/version brand rules, facts & assets; inspect Ambiguity Radar, Impact Analysis & Settings |
| **Creator** (`creator`) | `creator@meridian.flow` | `password123` | Upload drafts (`.md`, `.txt`, `.pdf`, `.docx`, `.png`, `.jpg`), set sensitivity, edit Intent Card, accept/dispute findings |
| **Brand Reviewer** (`reviewer`) | `reviewer@meridian.flow` | `password123` | Review terminology, tone, visual & accessibility queues; request changes or override with written reason |
| **Legal Reviewer** (`legal_reviewer`) | `legal@meridian.flow` | `password123` | Mandatory approver when claim-type findings (`outdated`, `contradicted`, `unsupported`) exist; hash-bound `POST /revisions/{id}/approve` |

### Secondary Tenant for RLS Isolation Testing: Acme Corporation (`tenant_acme`)

| Role | Email | Password | Purpose |
|---|---|---|---|
| **Acme Admin** (`admin`) | `admin@acme.com` | `password123` | Proves PostgreSQL Row-Level Security (`SET LOCAL app.tenant_id`) prevents cross-tenant source/content access |
| **Acme Creator** (`creator`) | `creator@acme.com` | `password123` | Cross-tenant isolation verification |

---

## Docker Compose Quickstart (Full Stack)

System packages required by the multimodal engine (`tesseract-ocr`, `tesseract-ocr-eng`, `libgl1`, `libglib2.0-0`, `libpq-dev`) are baked directly into [`api/Dockerfile`](api/Dockerfile).

1. **Start infrastructure, database (`pgvector/pgvector:pg16`), MinIO, FastAPI, and Next.js:**
   ```bash
   docker compose up --build -d
   ```
   The API container automatically runs `alembic upgrade head` on boot before launching Uvicorn on port `8000`.

2. **Seed Meridian Flow brand kit, Acme RLS tenant, and judge accounts:**
   ```bash
   docker compose exec api python scripts/seed.py
   ```

3. **Optional — Populate labelled synthetic calibration history through real API endpoints:**
   ```bash
   docker compose exec api python scripts/generate_synthetic_history.py --base-url http://localhost:8000
   ```

4. **Verify audit hash-chain integrity:**
   ```bash
   docker compose exec api python scripts/verify_audit_chain.py
   ```

5. **Open the workspace:**
   - Web UI: `http://localhost:3000`
   - FastAPI interactive docs: `http://localhost:8000/docs`

### Local Test Execution

- **Platform & Golden-Path CI tests:**
  ```bash
  PYTHONPATH=. pytest tests/api/ -v
  python scripts/verify_audit_chain.py
  ```
- **Full Python suite:**
  ```bash
  PYTHONPATH=. pytest -v
  ```
- **Frontend Vitest + `axe-core` WCAG checks & production build:**
  ```bash
  cd web && npm ci && npm test && npm run build
  ```

---

## Role & R1 Terminology Map (PRD §2.3)

| Round 2 Term | R1 Body Term | Implementation Location |
|---|---|---|
| **Guideline Compiler** | Versioned Knowledge Base import + ingest collision/lint check | [`engine/compiler.py`](engine/compiler.py), [`api/src/routers/sources.py`](api/src/routers/sources.py) |
| **Temporal Fact Ledger** | Fact versioning & superseded-claim detection | [`engine/fact_ledger.py`](engine/fact_ledger.py), `source_versions` |
| **Citation Verifier Node** | Anti-hallucination receipt gate | [`engine/verifier.py`](engine/verifier.py) |
| **Hybrid BM25 / pgvector RRF** | Lexical + vector retrieval & Reciprocal Rank Fusion (`k=60`) | [`engine/retrieval.py`](engine/retrieval.py) |

---

## Plan vs. Built Table (Round 2 Progress)

| R1 / PRD Feature | Tier | Status | Notes / Scope Justification |
|---|---|---|---|
| Monorepo, Docker Compose (`pgvector`, MinIO, API, Web), CI | P0 | **Shipped** | Configured in [`docker-compose.yml`](docker-compose.yml), [`api/Dockerfile`](api/Dockerfile), [`web/Dockerfile`](web/Dockerfile), and [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |
| PostgreSQL 16 + `pgvector` schema (13 tables) & non-owner RLS (`axiom_app`) | P0 | **Shipped** | Alembic migrations `001` & `002`; tenant scoping via `SET LOCAL app.tenant_id` |
| Idempotent Meridian Flow brand kit seed & JWT RBAC (4 roles + 2nd tenant) | P0 | **Shipped** | [`scripts/seed.py`](scripts/seed.py), [`api/src/routers/auth.py`](api/src/routers/auth.py) |
| Sources & version supersession API (`POST /sources`, `/versions`) + compile hook | P0 | **Shipped** | Hash-based idempotency + `ruleset_version` bumps on supersession |
| Content & Revision API (`POST /content`, `/{id}/revisions`) | P0 | **Shipped** | Sensitivity labels (`public`, `internal`, `restricted`), type allow-list, SHA-256 hashes |
| Review run trigger, composite run cache & stale-run watchdog | P0 | **Shipped** | Keyed by `(tenant_id, content_hash, ruleset_version, sensitivity, intent_card_hash)` |
| Finding decisions, mandatory override/dispute reasons (`422`), span comments | P0 | **Shipped** | Retry-idempotent decisions in [`api/src/routers/findings.py`](api/src/routers/findings.py) |
| State machine guards: SoD (`403`), mandatory `legal_reviewer` on claims, SHA-256 lock (`409`), edit invalidation | P0 | **Shipped** | Editing approved revisions creates `Invalidated (New Unapproved Revision)` |
| Append-only SHA-256 hash-chained `audit_log` + Postgres triggers + verifier CLI | P0 | **Shipped** | Revoked `UPDATE`/`DELETE` triggers + [`scripts/verify_audit_chain.py`](scripts/verify_audit_chain.py) |
| Usage ledger & Settings ("no external processing" switch & service catalog) | P0 | **Shipped** | `GET /usage`, `GET/PUT/PATCH /settings` |
| Light Mode Next.js Workspace, Receipt Cards, Diffs, Viewer (`react-pdf` + SVG `bbox`), Queue | P0 | **Shipped** | Exclusive Light Mode soft-pastel UI (`web/src/`) with Loading/Empty/Error states & keyboard nav |
| **I1:** Hybrid `rank_bm25` + `pgvector` RRF claim ledger & Citation Verifier | P1 | **Shipped** | Deterministic fact chains (`F-112`, `F-108`, `F-115`), hybrid fallback & verifier drop metrics |
| **I2:** Measured WCAG contrast & CIEDE2000 palette checks (`ΔE`) + OCR | P1 | **Shipped** | Normalized `[page, x0, y0, x1, y1]` overlays + contrast/palette thresholds |
| **I3:** Guideline Ambiguity Radar (`rule_stats`), `GET /impact?source_id=`, Synthetic History | P1 | **Shipped** | Flags 4/4 seeded ambiguous rules (`0` false flags on controls); includes `supported_claim` impact |
| Recurring Insights dashboard (`GET /insights/recurring`) | P1 | **Shipped** | Rule/type/severity/content hotspot breakdowns with explicit synthetic disclosures |
| Intent Card extraction & LLM minimal-edit fix re-check (`T9`) | P1 | **Shipped** | Non-blocking Intent Card drawer + `recheck_fix` verification loop |
| Human-in-the-loop LangGraph interrupt suspension | Deviation | **Partial** | Replaced suspended graph thread with PostgreSQL state-machine handoff (recorded in `docs/ARCHITECTURE.md`) |
| Logo clear-space multi-scale matching & PDF rule extraction | P2 | **Deferred** | Scoped to post-hackathon / P2 cleanup if time permits per §6 cut order |
| Local-model inference mode, webhooks, SSO connectors, PDF export, malware AV | Round 3 | **Deferred** | Explicitly out of scope for Round 2 (PRD §1.3) |

---

## Disclosures & Documentation

- Architecture & Technical Decisions: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- AI Models, ZDR Terms, Data Sent, Licenses & AI-Assistant Use: [`docs/DISCLOSURES.md`](docs/DISCLOSURES.md)
- Usability Testing Protocol & Evidence Log: [`docs/user-testing/USABILITY_TEST_TEMPLATE.md`](docs/user-testing/USABILITY_TEST_TEMPLATE.md)
- Team Contributions: [`CONTRIBUTIONS.md`](CONTRIBUTIONS.md)

