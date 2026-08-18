"""
train_model.py
Trains a fully local sentence-level classifier on government_sentiment_dataset.csv.
No API key, no internet needed at inference time.

Predicts `tier` (1=neutral/lawful, 2=abusive, 3=hate/incitement, 4=threat)
directly from the whole sentence using TF-IDF + Logistic Regression.

Usage:
    python train_model.py
    (produces tier_model.pkl in the same folder)
"""

import csv
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

DATA_PATH = "government_sentiment_dataset.csv"
MODEL_PATH = "tier_model.pkl"


def load_data(path):
    texts, tiers = [], []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cleaned = {
                k.strip().strip('"').strip(): v.strip().strip('"').strip()
                for k, v in row.items()
                if k is not None and v is not None
            }
            texts.append(cleaned["text"])
            tiers.append(int(cleaned["tier"]))
    return texts, tiers


def main():
    texts, tiers = load_data(DATA_PATH)
    print(f"Loaded {len(texts)} labeled sentences.")

    # Small dataset -> keep the split modest so we still have enough to train on.
    X_train, X_test, y_train, y_test = train_test_split(
        texts, tiers, test_size=0.2, random_state=42, stratify=tiers
    )

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])

    pipeline.fit(X_train, y_train)

    print("\n--- Evaluation on held-out test split ---")
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred, zero_division=0))

    joblib.dump(pipeline, MODEL_PATH)
    print(f"Model saved to {MODEL_PATH}")
    print(
        "\nNOTE: this is trained on a small seed dataset (~60 rows). Treat "
        "test-split accuracy as a rough signal, not a final metric — expand "
        "government_sentiment_dataset.csv with more examples for a more "
        "reliable model before relying on this beyond the demo."
    )


if __name__ == "__main__":
    main()