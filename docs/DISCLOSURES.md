# Technology, Model, Service, License & AI Assistance Disclosures

> In compliance with PRD §2.2, §4.5, and R1 §5.2, this document discloses all external services, AI models, open-source libraries, datasets, and AI coding assistant usage across Axiom.

---

## 1. Configured External Services & LLM Data-Retention Disclosure (Platform & Engine)

Axiom routes external calls exclusively through policy-gated services (mirrored in [`api/src/services/governance.py`](../api/src/services/governance.py) `EXTERNAL_SERVICES_CATALOG` and exposed in the in-app `GET /settings` view):

| Service / Provider | Configured Model / Tier | Purpose | External Call? | ZDR / Retention Terms | Exact Data Categories Sent | Sensitivity Policy Enforcement |
|---|---|---|---|---|---|---|
| **OpenRouter / Anthropic (`LLMClient`)** | Fast tier: `claude-3-5-haiku-20241022` / Strong tier (`gpt-4o-mini` / `claude-3-5-sonnet` configurable) | Intent Card extraction, claim disambiguation fallback, tone evaluation, minimal-edit fix generation (`temperature=0`, JSON-schema constrained) | **Yes** (`public` / `internal` only) | API Zero-Data-Retention / non-training enterprise API endpoints; payloads not retained for model training | Strict `<untrusted_document_span>`-delimited `ContentUnit` excerpt, Intent Card (`purpose`, `audience`, `key_message`, `cta`), and matched rule/fact snippets only (never full tenant DB) | **Hard-blocked on `restricted` sensitivity** and when tenant `no_external_processing = true` (`0` external calls, `0` tokens, `$0.00` cost verified in `usage_ledger`) |
| **Google Gemini API** *(optional multimodal)* | Gemini Flash / Pro multimodal | Optional multimodal visual/accessibility review for uploaded banner images | **Yes** (`public` / `internal` only) | Paid/enterprise API tier with training opt-out / ZDR configuration | Uploaded image region + accessibility rubric prompt only | **Hard-blocked on `restricted` sensitivity** and when `no_external_processing = true` |
| **Local Sentence-Transformers (`BAAI/bge-small-en-v1.5`)** | `BAAI/bge-small-en-v1.5` (`384-d`) | Local dense embeddings for vector retrieval and intent similarity | **No (100% local)** | In-process container memory only | None leaves deployment boundary | Allowed for all sensitivities including `restricted` |
| **Deterministic Pipeline & Tesseract OCR** | Tesseract 5 + Python rules / `scikit-image` / `rank_bm25` | Terminology matching, temporal fact lookup, BM25, WCAG contrast, CIEDE2000 ΔE, OCR | **No (100% local)** | In-process execution only | None leaves deployment boundary | Allowed for all sensitivities including `restricted` |

---

## 2. Platform & Engine Stack Disclosures (PRD §2.2)

### Yash's Platform Stack (`api/` & `web/`)

| Component | Technology / Package | License | Purpose | Data Boundary |
|---|---|---|---|---|
| **Web Frontend** | Next.js 14, React 18, TypeScript, Tailwind CSS | MIT | Exclusive Light Mode review workspace, Admin/Creator/Reviewer queues, Ambiguity Radar & Insights dashboards | Client/Host |
| **PDF & BBox Overlay** | `react-pdf` (`pdfjs-dist`), inline SVG (`viewBox="0 0 1 1"`) | MIT / Apache-2.0 | PDF rendering and zoom-invariant normalized bounding-box selection | Client |
| **Tracked-Change Diffs** | `diff` (`diffWords`) | BSD-3-Clause | Word-level inline suggested fix & revision comparison diffs | Client |
| **Accessibility Testing** | `axe-core` (`lucide-react` icons) | MPL-2.0 / ISC | Partial automated WCAG 2.2 AA DOM/ARIA validation in CI (`vitest`) | Dev / CI |
| **Backend API** | FastAPI, Pydantic v2, Uvicorn, PyJWT, bcrypt, httpx | MIT / BSD / Apache-2.0 | REST endpoints, RBAC, run cache, state machine guards, audit chain | API Container |
| **Database & Migrations** | PostgreSQL 16 (`pgvector`), SQLAlchemy 2, Alembic, `psycopg` | PostgreSQL / MIT / LGPL | 13-table schema, `vector(384)`, RLS (`SET LOCAL app.tenant_id`), append-only audit triggers | DB Host |
| **Object Storage** | MinIO / S3-compatible storage | AGPL-3.0 (MinIO server) | Original uploaded drafts and derived artifacts | Storage Host |
| **CI/CD & Testing** | GitHub Actions, `pytest`, `pytest-asyncio`, Vitest | MIT / Apache-2.0 | Automated DB migrations, platform golden-path tests, frontend build & accessibility checks | CI Runner |

### Ayush's Engine Libraries & Reference Licenses

| Library | License | Disclosure / Notes |
|---|---|---|
| `PyMuPDF` (`fitz`) | **AGPL-3.0** | Used for character-level PDF spans (`rawdict`), font metadata, and normalized bounding boxes. Disclosed per PRD §2.2; repository license must remain AGPL-3.0 compatible or swap to permissive `pdfplumber` (MIT) if proprietary licensing is required. |
| `python-docx`, `markdown-it-py`, `rank-bm25`, `textstat` | MIT / Apache-2.0 | Document unit parsing, BM25 lexical index, and readability scoring. |
| `opencv-python`, `Pillow`, `scikit-image`, `numpy`, `pytesseract` | Apache-2.0 / BSD | Image processing, CIEDE2000 ΔE math, and Tesseract 5 OCR word-box extraction. |

---

## 3. Datasets & Reference Benchmarks

- **No third-party training datasets used:** Brand governance rules, glossary terms, versioned facts (`F-112`, `F-108`, `F-115`), palette, and logo fixtures belong strictly to the team-authored **Meridian Flow** fictional brand kit (`brand_kit/`).
- **Synthetic Radar History:** Synthetic reviewer decisions generated for Ambiguity Radar calibration (`scripts/generate_synthetic_history.py`) are executed through real API routes and explicitly tagged `synthetic: true` / `Synthetic` in API payloads and the UI.
- **Published Reference Standards:** WCAG 2.2 relative-luminance contrast formulas and Sharma, Wu & Dalal (2005) published CIEDE2000 reference pairs are used strictly as mathematical test fixtures.

---

## 4. AI Coding Assistant Disclosure (Boilerplate & Development Assistance)

> **Usage Disclosure (PRD §2.2 & R1 Submission Rules):** Portions of boilerplate scaffolding, test fixture authoring, refactoring helpers, UI layout refinement, and documentation drafting in this repository were assisted by AI coding assistants (Google Antigravity / Claude / Gemini coding agents) under direct human specification, architectural review, code inspection, and CI verification by the team leads. All cryptographic integrity checks, Row-Level Security policies, state-machine guards, evaluation tests, and golden-path assertions were executed and verified locally and in GitHub Actions CI before commit.

