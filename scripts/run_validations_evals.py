#!/usr/bin/env python3
"""
Run all validations and evals and print a clear report.

Usage (from pipeline project root):
  python scripts/run_validations_evals.py
  python scripts/run_validations_evals.py --json report.json
  python scripts/run_validations_evals.py --openai-key "sk-..."   # optional: run OpenAI parsing eval

Validations: cache exists, readable, required columns, min rows, metadata, key columns non-empty.
Evals: keyword query parsing, data coverage, role spread, optional OpenAI parsing.
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Project root = parent of scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "app"))

# Now import pipeline modules
from data_pipeline.validations import run_all_validations
from data_pipeline.evals import run_all_evals


def main():
    parser = argparse.ArgumentParser(description="Run validations and evals pipeline")
    parser.add_argument("--json", type=str, default="", help="Write full report to this JSON file")
    parser.add_argument("--min-rows", type=int, default=1, help="Min rows required for cache (default 1)")
    parser.add_argument("--openai-key", type=str, default="", help="OpenAI API key for OpenAI parsing eval (or set OPENAI_API_KEY)")
    args = parser.parse_args()
    openai_key = (args.openai_key or os.environ.get("OPENAI_API_KEY") or "").strip()

    run_at = datetime.now(timezone.utc).isoformat()
    print("=" * 60)
    print("VALIDATIONS & EVALS PIPELINE")
    print("=" * 60)
    print(f"Run at: {run_at}\n")

    # --- Validations ---
    print("VALIDATIONS")
    print("-" * 40)
    validation_results = run_all_validations(min_rows=args.min_rows)
    v_passed = sum(1 for r in validation_results if r.get("passed"))
    v_total = len(validation_results)
    for r in validation_results:
        status = "PASS" if r.get("passed") else "FAIL"
        symbol = "✓" if r.get("passed") else "✗"
        print(f"  {symbol} [{status}] {r['name']}: {r['message']}")
        if r.get("details"):
            for k, v in r["details"].items():
                print(f"      {k}: {v}")
    print(f"\n  Validations: {v_passed}/{v_total} passed\n")

    # --- Evals ---
    print("EVALS")
    print("-" * 40)
    eval_results = run_all_evals(openai_api_key=openai_key or None)
    for r in eval_results:
        score = r.get("score", 0)
        pct = score * 100
        print(f"  {r['name']}: {r['message']} (score: {pct:.0f}%)")
        if r.get("details"):
            d = r["details"]
            if "cases" in d:
                for c in d["cases"][:5]:
                    print(f"      - {c}")
            else:
                for k, v in d.items():
                    print(f"      {k}: {v}")
    print()

    # --- Summary ---
    print("SUMMARY")
    print("-" * 40)
    all_v = v_passed == v_total
    eval_scores = [r.get("score", 0) for r in eval_results]
    avg_eval = sum(eval_scores) / len(eval_scores) if eval_scores else 0
    print(f"  Validations: {'All passed' if all_v else f'{v_total - v_passed} failed'}")
    print(f"  Evals average score: {avg_eval*100:.0f}%")
    print("=" * 60)

    report = {
        "run_at": run_at,
        "validations": {
            "passed": v_passed,
            "total": v_total,
            "all_passed": all_v,
            "results": validation_results,
        },
        "evals": {
            "results": eval_results,
            "average_score": avg_eval,
        },
    }
    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"Report written to {out_path}")

    return 0 if all_v else 1


if __name__ == "__main__":
    sys.exit(main())
