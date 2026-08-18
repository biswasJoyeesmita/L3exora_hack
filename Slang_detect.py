"""
Eldorado - Slang Word Detection Model
Detection / Inference Script (interactive user input)
-----------------------------------------------------------
Loads a trained model and lets a user type in a sentence.
Each word is analyzed and flagged as SLANG or standard,
along with a confidence score.

Usage:
    python detect_slang.py --model slang_model.pkl
    python detect_slang.py --model slang_model.pkl --threshold 0.6
"""

import argparse
import os
import re
import joblib

TOKEN_PATTERN = re.compile(r"[A-Za-z']+")


def load_model(model_path):
    if not os.path.exists(model_path):
        raise FileNotFoundError(
            f"Model not found at: {model_path}. Train it first using train_model.py"
        )
    return joblib.load(model_path)


def tokenize(text):
    return TOKEN_PATTERN.findall(text)


def analyze_text(pipeline, text, threshold=0.5):
    tokens = tokenize(text)
    if not tokens:
        return []

    words_lower = [t.lower() for t in tokens]
    probs = pipeline.predict_proba(words_lower)[:, 1]  # probability of "slang" class

    results = []
    for original, word, prob in zip(tokens, words_lower, probs):
        label = "SLANG" if prob >= threshold else "standard"
        results.append({
            "word": original,
            "label": label,
            "confidence": round(float(prob), 3),
        })
    return results


def pretty_print(results):
    print("\n--- Eldorado Slang Detection Result ---")
    annotated = [f"[{r['word']}]*" if r["label"] == "SLANG" else r["word"] for r in results]
    print(" ".join(annotated))
    print("\nDetails:")
    for r in results:
        marker = "SLANG   " if r["label"] == "SLANG" else "standard"
        print(f"  {r['word']:<15} -> {marker}  (confidence: {r['confidence']})")
    print("----------------------------------------\n")


def main():
    parser = argparse.ArgumentParser(description="Eldorado interactive slang detector.")
    parser.add_argument("--model", default="slang_model.pkl", help="Path to trained model")
    parser.add_argument("--threshold", type=float, default=0.5, help="Slang classification threshold (0-1)")
    args = parser.parse_args()

    pipeline = load_model(args.model)
    print("=== Eldorado Slang Word Detector ===")
    print("Type a sentence to check for slang words. Type 'exit' or 'quit' to stop.\n")

    while True:
        text = input("Enter text: ").strip()
        if text.lower() in ("exit", "quit"):
            print("Goodbye!")
            break
        if not text:
            print("Please enter some text.\n")
            continue

        results = analyze_text(pipeline, text, threshold=args.threshold)
        pretty_print(results)


if __name__ == "__main__":
    main()