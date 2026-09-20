"""
run_eval_fast.py — Lexora 3-model evaluation runner.

Runs the lexicon, local RoBERTa, and Gemini classifiers against
lexora_test_dataset.json, writes per-item results to eval_full_results.json,
then prints a false-tier analysis report to stdout.

Run from any directory:
    python scratch/run_eval_fast.py [--dataset PATH] [--out PATH]

Environment:
    GEMINI_API_KEY must be set (or present in .env next to this script's package root).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve package root dynamically so this script runs correctly regardless
# of the working directory it is launched from.
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # scratch/
PACKAGE_ROOT = SCRIPT_DIR.parent                      # L3exora_hack/

if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

# Load .env from package root (GEMINI_API_KEY etc.)
from dotenv import load_dotenv
load_dotenv(PACKAGE_ROOT / ".env")

# ---------------------------------------------------------------------------
# CLI args — allow overriding dataset / output paths without editing the file
# ---------------------------------------------------------------------------
parser = argparse.ArgumentParser(description="Lexora model evaluation runner")
parser.add_argument(
    "--dataset",
    default=str(PACKAGE_ROOT / "lexora_test_dataset.json"),
    help="Path to evaluation dataset JSON (default: <package_root>/lexora_test_dataset.json)",
)
parser.add_argument(
    "--out",
    default=str(SCRIPT_DIR / "eval_full_results.json"),
    help="Path to write per-item results JSON (default: scratch/eval_full_results.json)",
)
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Load dataset
# ---------------------------------------------------------------------------
dataset_path = Path(args.dataset)
if not dataset_path.exists():
    sys.exit(f"[ERROR] Dataset not found: {dataset_path}")

with open(dataset_path, encoding="utf-8") as f:
    dataset = json.load(f)

print(f"Total dataset items: {len(dataset)}")
print(f"Dataset:             {dataset_path}")
print(f"Output:              {args.out}\n")

# ---------------------------------------------------------------------------
# Import classifiers (available once PACKAGE_ROOT is on sys.path)
# ---------------------------------------------------------------------------
import lexicon as lex_mod
import classify_local as local_mod
import classify as gemini_mod

# ---------------------------------------------------------------------------
# Run all three classifiers and collect per-item structured results
# ---------------------------------------------------------------------------
results_data = []
batch_size = 10

for i in range(0, len(dataset), batch_size):
    batch = dataset[i : i + batch_size]
    formatted = [{"text": d["query"], "context": d["category"]} for d in batch]

    # Gemini (batched)
    try:
        gemini_batch = gemini_mod.classify_batch(formatted)
    except Exception as e:
        print(f"  [!] Batch {i // batch_size + 1} Gemini error: {e}")
        gemini_batch = [{"tier": 1, "error": str(e)} for _ in batch]

    for item, g_res in zip(batch, gemini_batch):
        q = item["query"]
        l_res = lex_mod.check_lexicon(q)
        rob_res = local_mod.classify(q)

        results_data.append(
            {
                "id": item["id"],
                "query": q,
                "category": item["category"],
                "ground_truth": item["ground_truth"],
                "lexicon_tier": l_res.get("lexicon_tier") or 1,
                "roberta_tier": rob_res.get("tier", 1),
                "gemini_tier": g_res.get("tier", 1),
                "gemini_sentiment": g_res.get("overall_sentiment"),
                "gemini_justification": g_res.get("justification"),
                "gemini_terms": g_res.get("flagged_terms", []),
                "roberta_terms": rob_res.get("flagged_terms", []),
            }
        )

    print(f"  Processed items {i + 1}–{min(i + batch_size, len(dataset))}")

# ---------------------------------------------------------------------------
# Write JSON results
# ---------------------------------------------------------------------------
out_path = Path(args.out)
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results_data, f, indent=2)
print(f"\nSaved evaluation results → {out_path}\n")

# ---------------------------------------------------------------------------
# Analysis / false-tier report  (merged from evaluate_all.py)
# ---------------------------------------------------------------------------
def _false_tier_reason(gt: str, tier: int) -> str | None:
    if gt == "Non-Compliant / Harmful" and tier < 3:
        return f"FALSE NEGATIVE – under-classified (got Tier {tier}, expected Tier 3/4)"
    if gt == "Compliant / Safe" and tier > 1:
        return f"FALSE POSITIVE (got Tier {tier}, expected Tier 1)"
    if gt == "Compliant / Sensitive" and tier >= 3:
        return f"FALSE OVER-FLAGGING (got Tier {tier}, expected Tier 1/2)"
    return None


def analyze_model(model_name: str, tier_key: str) -> None:
    """Print tier distribution and false-tier cases for one model column."""
    print("=" * 54)
    print(f"  MODEL: {model_name}")
    print("=" * 54)

    cat_breakdown: dict[str, dict] = {}
    false_cases: list[dict] = []

    for row in results_data:
        cat = row["category"]
        gt = row["ground_truth"]
        tier = row.get(tier_key, 1)

        if cat not in cat_breakdown:
            cat_breakdown[cat] = {"total": 0, "tiers": {}}
        cat_breakdown[cat]["total"] += 1
        cat_breakdown[cat]["tiers"][tier] = cat_breakdown[cat]["tiers"].get(tier, 0) + 1

        reason = _false_tier_reason(gt, tier)
        if reason:
            false_cases.append(
                {
                    "id": row["id"],
                    "category": cat,
                    "ground_truth": gt,
                    "predicted_tier": tier,
                    "query": row["query"],
                    "reason": reason,
                    "justification": row.get("gemini_justification") if "gemini" in tier_key else None,
                    "matched_terms": row.get("gemini_terms") if "gemini" in tier_key else row.get("roberta_terms"),
                }
            )

    print("\n--- Tier distribution by category ---")
    for cat, info in cat_breakdown.items():
        total = info["total"]
        print(f"\n  [{cat}]  (n={total})")
        for t in [1, 2, 3, 4]:
            c = info["tiers"].get(t, 0)
            print(f"    Tier {t}: {c:3d}  ({c / total * 100:.1f}%)")

    print(f"\n--- False-tier cases: {len(false_cases)} / {len(results_data)} ---")
    for ft in false_cases:
        print(f"\n  [ID {ft['id']}]  Category: {ft['category']}  |  GT: {ft['ground_truth']}")
        print(f"    Query:  \"{ft['query']}\"")
        print(f"    {ft['reason']}")
        if ft.get("justification"):
            print(f"    Justification: {ft['justification']}")
        if ft.get("matched_terms"):
            print(f"    Matched terms: {ft['matched_terms']}")
    print()


analyze_model("Lexicon Rule-Based Engine",         "lexicon_tier")
analyze_model("Local RoBERTa Transformer Engine",  "roberta_tier")
analyze_model("Gemini LLM Classifier",             "gemini_tier")
