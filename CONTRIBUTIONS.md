# Team Contribution Statements (`Axiom: Round 2`)

> **Team:** Hex & Web · Aligned with commit authorship and PRD Appendix A.

---

### Member 1 — Ayush Aryan (`Automated Multimodal Engine Lead`)

- **Owned Deliverables (`A-01`–`A-19`):**
  - **Contracts & Meridian Flow Brand Kit (`A-01`–`A-03`):** Typed Pydantic boundary contracts (`ContentUnit`, `Finding`, `ReviewResult`, `DisclosureRecord`), stub engine, and the **Meridian Flow** fictional brand kit (18 rules incl. 4 ambiguous + 4 clear controls, 14 versioned facts incl. `F-112`/`F-108`/`F-115` supersession chains, 24 glossary terms, palette and logo assets).
  - **Multimodal Ingest & LangGraph Pipeline (`A-04`–`A-07`):** Parsers for Markdown/text, PDF (`PyMuPDF` character boxes + colour/size), DOCX (`python-docx`), and PNG/JPG (`Tesseract OCR`), emitting normalized `[page, x0, y0, x1, y1]` (`0.0–1.0`) bounding boxes; LangGraph parallel DAG with sensitivity policy router; XML-sandboxed `LLMClient`; and **Guideline Compiler** (local `BAAI/bge-small-en-v1.5` 384-d embeddings, `rank_bm25` index, rule-collision and missing-owner/example lint).
  - **Checkers, Verifier & Intent-Preserving Fixes (`A-08`–`A-16`):** Deterministic terminology checker; **Temporal Fact Ledger** claim extraction, tuple normalisation, superseded-version lookup, and hybrid `rank_bm25` + `pgvector` RRF retrieval with retrieval traces (Improvement 1); **Citation Verifier** anti-hallucination gate; WCAG 2.2 contrast, CIEDE2000 (`scikit-image`) palette distance, OCR confidence validation, and logo/clear-space checks (Improvement 2); tone checker; and Intent Card + self-checking minimal-edit fix generator with superlative qualification.
  - **Evaluation & Reliability Suite (`A-17`–`A-19`):** 48-item evaluation dataset generator (`eval/build_dataset.py`), single-prompt baseline runner, Sharma et al. (2005) CIEDE2000 & WCAG boundary unit tests, 4-vector prompt-injection suite, and engine evaluation notes/disclosure rows.
- **Verification Commands:**
  ```bash
  PYTHONPATH=. pytest tests/test_issue*.py -v
  ```
  Verifies citation verifiability, CIEDE2000/WCAG mathematical accuracy, Restricted-mode zero-external-call enforcement, and Improvement 1 & 2 benchmarks.

---

### Member 2 — Yashkumar Nimje (`Full-Stack Product & Governance Lead`)

- **Owned Deliverables (`Y-01`–`Y-27`):**
  - **Platform, PostgreSQL + `pgvector` Schema & RLS (`Y-01`–`Y-05`):** Monorepo & Docker Compose infrastructure (`api/Dockerfile` with Tesseract/OpenCV packages, `web/Dockerfile`, `docker-compose.yml`), Alembic migrations (`001`, `002`) for all 13 R1 §3.5 tables with `vector(384)`, idempotent brand-kit seed runner (`scripts/seed.py`), JWT auth for 4 seeded Meridian Flow roles + Acme tenant, and PostgreSQL Row-Level Security (`SET LOCAL app.tenant_id` under non-owner DB role `axiom_app`).
  - **FastAPI Endpoints, Caching & Governance State Machine (`Y-06`–`Y-15`):** All R1 §3.6 REST endpoints (`/sources`, `/content`, `/revisions`, `/findings`, `/comments`, `/approve`, `/insights`, `/impact`, `/audit`, `/usage`, `/settings`), composite-keyed run cache + stale-run watchdog, role-based finding routing, separation-of-duties (`403` on self-approval), mandatory legal sign-off on claim findings, SHA-256 content-hash-bound approval locks (`409` on stale hash, automatic `Invalidated (New Unapproved Revision)` status on edit), append-only hash-chained `audit_log` with PostgreSQL `UPDATE`/`DELETE` triggers + [`scripts/verify_audit_chain.py`](scripts/verify_audit_chain.py), and `usage_ledger` persistence.
  - **Next.js Review Workspace & Bounding-Box UI (`Y-16`–`Y-20`):** Brand-Ops Admin source/version UI, Creator upload & non-blocking Intent Card drawer, evidence-first Receipt Cards with tracked-change diffs (`diff`), `"Assisted"` / `"Assisted Fix"` badges, keyboard navigation, Light Mode soft-pastel design system with explicit loading/empty/error states, interactive PDF/image viewer (`react-pdf`) with normalized SVG bounding-box overlays and two-way card-to-span selection, and Reviewer queue UI.
  - **Ambiguity Radar, Impact Analysis & Usability Evidence (`Y-21`–`Y-27`):** Live SQL signal aggregation for the **Ambiguity Radar** (`4/4` ambiguous rules flagged, `0` false flags on clear controls) and `GET /impact?source_id=` affected-content lookup including `supported_claim` matches (Improvement 3), Recurring Insights dashboard, labelled synthetic history generator ([`scripts/generate_synthetic_history.py`](scripts/generate_synthetic_history.py)), CI golden-path integration suite ([`tests/api/test_platform_y6.py`](tests/api/test_platform_y6.py)), `axe-core` WCAG accessibility verification, and usability testing protocol ([`docs/user-testing/USABILITY_TEST_TEMPLATE.md`](docs/user-testing/USABILITY_TEST_TEMPLATE.md)).
- **Verification Commands:**
  ```bash
  PYTHONPATH=. pytest tests/api/ -v
  python scripts/verify_audit_chain.py
  cd web && npm test && npm run build
  ```
  Verifies run caching/idempotency, tenant RLS isolation, separation of duties (`403`), hash-bound approval invalidation (`409`), override justification (`422`), audit hash-chain integrity, golden-path steps 1–7, Ambiguity Radar + Impact Analysis queries, and frontend accessibility/product checks.

