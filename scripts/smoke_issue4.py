"""Smoke test script for Issue #4 (A2 — Ingest & LangGraph pipeline, G1)."""

from pathlib import Path
from engine.parsers import parse_markdown
from engine.pipeline import run_review
from contracts.models import Sensitivity

print('=' * 65)
print('ISSUE #4 (A2 - Ingest & LangGraph pipeline, G1) SMOKE TEST')
print('=' * 65)

draft_path = Path('engine/fixtures/sample_draft.md')
draft_text = draft_path.read_text(encoding='utf-8')
print(f'1. Parsing Markdown draft ({len(draft_text)} chars)...')
units = parse_markdown(draft_text, revision_id='rev_g1_smoke')
print(f'   -> Extracted {len(units)} ContentUnits with exact offsets and bboxes:')
for u in units:
    print(f'      [{u.unit_id}] ({u.kind:9s}, offsets={u.offsets}): "{u.text[:40]}..."')

print('\n2. Executing Review Pipeline (policy=Sensitivity.internal)...')
result = run_review(units, ruleset_version=1, policy=Sensitivity.internal)
print(f'   -> ReviewResult: {len(result.findings)} findings, partial={result.partial}')
for f in result.findings:
    print(f'      * [{f.type.value.upper()}] Severity={f.severity.value}, Quote="{f.span.quote}"')
    print(f'        Explanation: {f.explanation}')
    if f.suggested_fix:
        print(f'        Suggested Fix: "{f.suggested_fix.text}"')
    print(f'        Route to: {f.route_to}, Evidence: {[e.source for e in f.evidence]}')

print('\n3. Progress Tracking Events:')
for p in result.run_progress:
    print(f'   - Node: {p.node:12s} Status: {p.status.value:8s} Error: {p.error}')

print('\n4. Testing Restricted Run Policy Enforcement:')
restr_res = run_review(units, ruleset_version=1, policy=Sensitivity.restricted)
external_calls = [d for d in restr_res.disclosures if d.external_call]
total_cost = sum(d.cost or 0.0 for d in restr_res.disclosures)
print(f'   -> Restricted run findings: {len(restr_res.findings)}')
print(f'   -> External calls count: {len(external_calls)} (Expected: 0)')
print(f'   -> Total external cost: ${total_cost:.2f} (Expected: $0.00)')
assert len(external_calls) == 0, 'Restricted run made external call!'

print('\n5. Testing Graceful Degradation on LLM Failure:')
fail_res = run_review(units, ruleset_version=1, policy=Sensitivity.internal, simulate_llm_failure=True)
print(f'   -> Partial flag: {fail_res.partial} (Expected: True)')
print(f'   -> Deterministic findings preserved: {len(fail_res.findings)} (Expected >= 2)')
assert fail_res.partial is True
assert len(fail_res.findings) >= 2

print('\n[SUCCESS] ALL GATE G1 ACCEPTANCE CRITERIA VERIFIED!')
print('=' * 65)

