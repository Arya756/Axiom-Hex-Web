# Usability Testing Protocol & Evidence Log (PRD §5.4 / Y-27)

> **Owner:** Yashkumar Nimje · **Participants target:** 3–5 external evaluators outside the Hex & Web team  
> **Task Design:** Counterbalanced within-subject comparison between **Axiom Light Mode Workspace** and **Manual PDF Brand Guideline Review** across 2 equivalent drafts (Draft A vs Draft B), alternating draft order per participant.

---

## 1. Consent & Session Checklist

- [ ] Participant informed that session metrics (task completion, elapsed time, error count, clarity rating `1–5`, and think-aloud notes) are recorded for Axiom Round 2 usability evaluation (`Y-27`).
- [ ] Verbal or written consent recorded before starting timer (anonymized participant ID `P1`–`P5`; no PII stored).
- [ ] Role accounts ready (`creator@meridian.flow`, `reviewer@meridian.flow`, `legal@meridian.flow`).
- [ ] Product checks verified before session:
  - [ ] Evidence & verified citation receipts displayed **before** verdict/explanation.
  - [ ] Two-way selection synchronized between Finding Cards and Document Viewer highlights/SVG overlays.
  - [ ] Finding cards navigable via keyboard (`Tab`, `Enter`/`Space`, `ArrowDown`/`ArrowUp`).
  - [ ] Loading (`role="status"`), empty (`role="status"` + reset/upload action), and error (`role="alert"` + dismiss) states clearly visible.
  - [ ] Generated findings and fixes carry explicit **Assisted** / **Assisted Fix** badges.
  - [ ] Automated `axe-core` WCAG 2.2 AA check disclosed as **partial coverage** (`AxeDisclosure`), alongside manual keyboard/focus/label verification.

---

## 2. Task Script

1. **Condition A — Axiom Workspace:**
   - **Creator Task:** Upload a draft (`internal` sensitivity), review the Intent Card constraints, inspect finding receipts (Outdated fact, Banned terminology, Unsupported claim, Low-contrast graphic), accept a tracked-change fix, and dispute one subjective finding with a written justification reason.
   - **Reviewer / Legal Task:** Switch to Reviewer/Legal role, inspect revision diff, override or approve bound to the SHA-256 content hash, and verify invalidation upon subsequent edit.
2. **Condition B — Manual Baseline (PDF Guideline Only):**
   - Inspect a comparable draft alongside the static Meridian Flow PDF guideline document and list violations, out-of-date stats, and suggested corrections manually.

*(Alternate order across participants: Odd IDs (`P1`, `P3`, `P5`) run Condition A then Condition B; Even IDs (`P2`, `P4`) run Condition B then Condition A.)*

---

## 3. Participant Session Log Template

Copy one row/section per participant (`P1`–`P5`):

### Summary Table

| Participant | Consent Obtained | Order (`A->B` / `B->A`) | Role Tasks Completed (Creator / Reviewer) | Axiom Time (mm:ss) | Manual Time (mm:ss) | Errors / Friction Count | Clarity Rating (`1–5`) |
|---|---|---|---|---|---|---|---|
| `P1` | `[Yes/No]` | `A -> B` (Draft A / Draft B) | `[Pass/Partial]` | `00:00` | `00:00` | `0` | `_/5` |
| `P2` | `[Yes/No]` | `B -> A` (Draft B / Draft A) | `[Pass/Partial]` | `00:00` | `00:00` | `0` | `_/5` |
| `P3` | `[Yes/No]` | `A -> B` (Draft A / Draft B) | `[Pass/Partial]` | `00:00` | `00:00` | `0` | `_/5` |
| `P4` *(optional)* | `[Yes/No]` | `B -> A` | `[Pass/Partial]` | `00:00` | `00:00` | `0` | `_/5` |
| `P5` *(optional)* | `[Yes/No]` | `A -> B` | `[Pass/Partial]` | `00:00` | `00:00` | `0` | `_/5` |

### Think-Aloud Observations & UI Changes Made in Response

#### Participant `P1`
- **Consent:** Recorded `[Date / Initials]`
- **Think-aloud notes:**
  - *Upload & Intent Card:* `...`
  - *Receipt Cards & Highlight Sync:* `...`
  - *Dispute / Reviewer Approval & Hash Lock:* `...`
- **Observed errors / hesitations:** `...`
- **Changes made in response:** `...` *(link commit or UI component changed)*

#### Participant `P2`
- **Consent:** Recorded `[Date / Initials]`
- **Think-aloud notes:** `...`
- **Observed errors / hesitations:** `...`
- **Changes made in response:** `...`

#### Participant `P3`
- **Consent:** Recorded `[Date / Initials]`
- **Think-aloud notes:** `...`
- **Observed errors / hesitations:** `...`
- **Changes made in response:** `...`

---

## 4. Automated & Manual Accessibility Evidence Summary

- **Automated check (`vitest run`):**
  - `src/test/accessibility.test.tsx` (`AxeDisclosure` + `FindingCard` with `axe-core`)
  - `src/test/radar_insights.test.tsx` (`AmbiguityRadar`, `AffectedContentPanel`, `RecurringInsightsDashboard`)
  - `src/test/accessibility_product_y6.test.tsx` (Full `Home` workspace structural/ARIA checks, keyboard `ArrowUp`/`ArrowDown`/`Enter`/`Space` navigation, Loading/Empty/Error states, `Assisted` + `Assisted Fix` badges)
- **Manual keyboard & focus pass:** Verified visible Tailwind `focus-visible:ring-2` rings across workspace navigation tabs, upload/intent controls, finding cards, dispute forms, and reviewer action buttons without keyboard focus traps.
- **Coverage limitation:** As documented in [`AxeDisclosure.tsx`](../../web/src/components/common/AxeDisclosure.tsx), automated `axe-core` coverage targets DOM, ARIA roles, landmark structure, and focusable controls in jsdom and is reported as partial coverage rather than formal full WCAG 2.2 AA certification.

