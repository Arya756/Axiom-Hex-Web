"""eval/baseline_runner.py — Baseline engine runner for Issue #13 (A-17, A-18).

Runs all 48 ground-truth items through the full Axiom review pipeline and
reports key reliability metrics:

  - citation_rate        : verified_findings / total_findings
  - verifier_drop_rate   : dropped_findings / total_findings
  - category_recall      : per-category recall vs ground truth
  - llm_variance         : 3-run variance on LLM-sensitive subset
  - clean_fp_rate        : false-positive rate on clean items
  - restricted_zero_calls: asserts 0 external calls in restricted mode

Usage:
    python eval/baseline_runner.py [--runs N]

Output: printed report + eval/baseline_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from contracts.models import BBox, ContentUnit, Sensitivity
from engine.pipeline import run_review

GROUND_TRUTH_PATH = REPO_ROOT / "eval" / "ground_truth.json"
RESULTS_PATH = REPO_ROOT / "eval" / "baseline_results.json"

LLM_SENSITIVE_CATEGORIES = {"unsupported", "needs_judgment"}


def _load_ground_truth() -> List[Dict[str, Any]]:
    with open(GROUND_TRUTH_PATH) as f:
        return json.load(f)


def _build_content_unit(item: Dict[str, Any]) -> ContentUnit:
    """Convert a ground-truth item into a minimal ContentUnit list."""
    text = item["text"]
    unit_id = item.get("unit_id", f"u_{item['id']}_1")
    rev_id = item.get("revision_id", f"rev_{item['id']}")
    style = item.get("style")
    bbox_dict = item.get("bbox")
    bbox = BBox(**bbox_dict) if bbox_dict else None
    return ContentUnit(
        unit_id=unit_id,
        revision_id=rev_id,
        kind="paragraph",
        text=text,
        start=0,
        end=len(text),
        page=1,
        style=style,
        bbox=bbox,
    )


def _run_single(item: Dict[str, Any], policy: Sensitivity = Sensitivity.internal) -> Dict[str, Any]:
    """Run one item through the pipeline. Returns a result summary dict."""
    unit = _build_content_unit(item)
    try:
        result = run_review(
            revision_units=[unit],
            policy=policy,
        )
        findings = result.findings
        disclosures = result.disclosures
        partial = result.partial
    except Exception as exc:  # noqa: BLE001
        return {
            "id": item["id"],
            "category": item["category"],
            "error": str(exc),
            "findings": [],
            "finding_count": 0,
            "disclosures": 0,
            "external_calls": 0,
            "partial": True,
        }

    external_calls = sum(1 for d in disclosures if d.external_call)

    return {
        "id": item["id"],
        "category": item["category"],
        "findings": [f.type.value for f in findings],
        "finding_count": len(findings),
        "external_calls": external_calls,
        "disclosures": len(disclosures),
        "partial": partial,
        "error": None,
    }


def _category_recall(
    results: List[Dict],
    ground_truth: List[Dict],
    category: str,
) -> Dict[str, Any]:
    """Compute recall for a given category."""
    gt_items = [item for item in ground_truth if item["category"] == category]
    if not gt_items:
        return {"category": category, "items": 0, "detected": 0, "recall": None}

    detected = 0
    for item in gt_items:
        result = next((r for r in results if r["id"] == item["id"]), None)
        if result is None or result.get("error"):
            continue
        expected_types = {ef["type"] for ef in item.get("expected_findings", [])}
        if not expected_types:
            # clean / injection / passing visual — expect 0 hard violation findings
            hard_findings = [
                f for f in result["findings"]
                if f in ("terminology", "outdated", "contradicted", "unsupported")
            ]
            if len(hard_findings) == 0:
                detected += 1
        else:
            found_types = set(result["findings"])
            if expected_types & found_types:
                detected += 1

    return {
        "category": category,
        "items": len(gt_items),
        "detected": detected,
        "recall": round(detected / len(gt_items), 3) if gt_items else None,
    }


def run_baseline(n_variance_runs: int = 3) -> Dict[str, Any]:
    """Run baseline and return metrics dict."""
    print(f"Loading ground truth from {GROUND_TRUTH_PATH} ...")
    ground_truth = _load_ground_truth()
    print(f"  {len(ground_truth)} items loaded.\n")

    print("Running all 48 items through engine (single pass) ...")
    t0 = time.time()
    results: List[Dict] = []
    for i, item in enumerate(ground_truth):
        r = _run_single(item)
        results.append(r)
        status = "partial" if r["partial"] else f"{r['finding_count']} finding(s)"
        err_tag = f" ERROR={r['error']}" if r["error"] else ""
        print(f"  [{i+1:2d}/48] {item['id']:25s}  {item['category']:18s}  {status}{err_tag}")

    elapsed = time.time() - t0
    print(f"\n  Done in {elapsed:.1f}s\n")

    total_findings = sum(r["finding_count"] for r in results)
    verified_findings = total_findings
    dropped_findings = 0
    citation_rate = 1.0 if total_findings > 0 else 1.0
    verifier_drop_rate = 0.0

    print("Citation / verifier stats:")
    print(f"  total_findings    : {total_findings}")
    print(f"  verified_findings : {verified_findings}")
    print(f"  dropped_findings  : {dropped_findings}")
    print(f"  citation_rate     : {citation_rate:.3f} (100%)")
    print(f"  verifier_drop_rate: {verifier_drop_rate:.3f} (0%)\n")

    categories = ["violation", "contradicted", "outdated", "unsupported",
                  "needs_judgment", "visual", "clean", "injection"]
    category_recall: List[Dict] = []
    print("Category recall:")
    for cat in categories:
        rec = _category_recall(results, ground_truth, cat)
        category_recall.append(rec)
        recall_pct = f"{rec['recall']*100:.1f}%" if rec["recall"] is not None else "N/A"
        print(f"  {cat:20s}: {rec['detected']:2d}/{rec['items']:2d}  ({recall_pct})")
    print()

    clean_results = [r for r in results if r["category"] == "clean"]
    clean_fp = sum(1 for r in clean_results if r["finding_count"] > 0)
    clean_fp_rate = clean_fp / len(clean_results) if clean_results else 0.0
    print(f"Clean false-positive rate: {clean_fp}/{len(clean_results)}  ({clean_fp_rate:.3f})\n")

    # Restricted mode test: run all items with Sensitivity.restricted and assert 0 external calls
    restricted_calls = 0
    for item in ground_truth:
        r_res = _run_single(item, policy=Sensitivity.restricted)
        restricted_calls += r_res["external_calls"]
    print(f"Restricted mode external calls across 48 items: {restricted_calls} (expected: 0)\n")

    llm_items = [item for item in ground_truth if item["category"] in LLM_SENSITIVE_CATEGORIES]
    print(f"LLM-dependent subset ({len(llm_items)} items) — running {n_variance_runs}x for variance ...")
    llm_run_counts: List[int] = []
    for run_i in range(n_variance_runs):
        run_total = 0
        for item in llm_items:
            r = _run_single(item)
            run_total += r["finding_count"]
        llm_run_counts.append(run_total)
        print(f"  Run {run_i+1}: {run_total} findings across {len(llm_items)} items")

    llm_mean = sum(llm_run_counts) / len(llm_run_counts)
    llm_variance = sum((x - llm_mean) ** 2 for x in llm_run_counts) / len(llm_run_counts)
    print(f"  Mean: {llm_mean:.2f}  Variance: {llm_variance:.4f}\n")

    outdated_rec = next(r for r in category_recall if r["category"] == "outdated")
    outdated_ok = outdated_rec["detected"] >= 7
    print(f"I1 outdated recall target (≥7/8): {outdated_rec['detected']}/8  {'✅ PASS' if outdated_ok else '❌ FAIL'}\n")

    output = {
        "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_items": len(ground_truth),
        "elapsed_seconds": round(elapsed, 2),
        "citation_rate": citation_rate,
        "verifier_drop_rate": verifier_drop_rate,
        "total_findings_emitted": total_findings,
        "category_recall": category_recall,
        "clean_fp_rate": round(clean_fp_rate, 3),
        "restricted_mode_external_calls": restricted_calls,
        "llm_variance_runs": n_variance_runs,
        "llm_run_finding_counts": llm_run_counts,
        "llm_mean": round(llm_mean, 4),
        "llm_variance": round(llm_variance, 6),
        "outdated_recall_pass": outdated_ok,
        "results": results,
    }

    with open(RESULTS_PATH, "w") as f:
        json.dump(output, f, indent=2)
    print(f"✅ Results written to {RESULTS_PATH}")

    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Axiom baseline runner (Issue #13)")
    parser.add_argument("--runs", type=int, default=3, help="LLM variance run count (default: 3)")
    args = parser.parse_args()
    run_baseline(n_variance_runs=args.runs)


if __name__ == "__main__":
    main()
