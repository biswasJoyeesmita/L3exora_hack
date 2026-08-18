"""
run_tests.py
Runs the local classifier against EVERY row in government_sentiment_dataset.csv,
compares predicted tier/label against the ground-truth labels, and writes a
clean, structured report to output.txt (plus a summary to the terminal).

Usage:
    python run_tests.py
"""

import csv
from classify_local import classify

DATA_PATH = "government_sentiment_dataset.csv"
OUTPUT_PATH = "output.txt"


def predicted_label_from_tier(tier: int) -> int:
    # tier 1 = neutral/lawful -> label 0; tier 2+ = abusive/harmful -> label 1
    return 0 if tier == 1 else 1


def main():
    with open(DATA_PATH, newline="", encoding="utf-8") as f:
        rows = []
        for row in csv.DictReader(f):
            cleaned = {
                k.strip().strip('"').strip(): v.strip().strip('"').strip()
                for k, v in row.items()
                if k is not None and v is not None
            }
            rows.append(cleaned)

    print(f"Loaded {len(rows)} rows from {DATA_PATH}. Running classifier on all of them...\n")

    report_lines = []
    report_lines.append("=" * 100)
    report_lines.append("LEXORA — CLASSIFICATION TEST REPORT")
    report_lines.append(f"Total sentences tested: {len(rows)}")
    report_lines.append("=" * 100)
    report_lines.append("")

    correct_label = 0
    correct_tier = 0
    mismatches = []

    for i, row in enumerate(rows, start=1):
        text = row["text"]
        true_label = int(row["label"])
        true_tier = int(row["tier"])
        style = row.get("style_note", "")

        result = classify(text)
        pred_tier = result["tier"]
        pred_label = predicted_label_from_tier(pred_tier)

        label_ok = pred_label == true_label
        tier_ok = pred_tier == true_tier
        correct_label += int(label_ok)
        correct_tier += int(tier_ok)

        status = "PASS" if label_ok else "FAIL"
        if not label_ok:
            mismatches.append((i, text, true_label, pred_label, true_tier, pred_tier))

        report_lines.append(f"[{i:02d}] {status}  (style: {style})")
        report_lines.append(f"     Text        : {text}")
        report_lines.append(f"     True        : label={true_label}  tier={true_tier}")
        report_lines.append(f"     Predicted   : label={pred_label}  tier={pred_tier}  source={result['source']}")
        report_lines.append(f"     Gov. target : {result['government_target_referenced']}  ({result['target_description']})")
        if result["flagged_terms"]:
            report_lines.append(f"     Flagged     : {', '.join(result['flagged_terms'])}")
        report_lines.append("-" * 100)

    total = len(rows)
    label_acc = correct_label / total * 100
    tier_acc = correct_tier / total * 100

    report_lines.append("")
    report_lines.append("=" * 100)
    report_lines.append("SUMMARY")
    report_lines.append("=" * 100)
    report_lines.append(f"Label accuracy (0=neutral vs 1=abusive) : {correct_label}/{total}  ({label_acc:.1f}%)")
    report_lines.append(f"Exact tier accuracy (1-4)               : {correct_tier}/{total}  ({tier_acc:.1f}%)")
    report_lines.append("")

    if mismatches:
        report_lines.append(f"Mismatched cases ({len(mismatches)}):")
        for idx, text, tl, pl, tt, pt in mismatches:
            report_lines.append(f"  [{idx:02d}] true_label={tl} pred_label={pl} | true_tier={tt} pred_tier={pt} | {text}")
    else:
        report_lines.append("No mismatches — all sentences classified correctly.")

    report_text = "\n".join(report_lines)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)

    # Print just the summary to terminal (full detail is in output.txt)
    print(f"Label accuracy: {correct_label}/{total} ({label_acc:.1f}%)")
    print(f"Tier accuracy : {correct_tier}/{total} ({tier_acc:.1f}%)")
    print(f"\nFull structured report written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()