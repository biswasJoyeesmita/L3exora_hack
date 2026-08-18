"""
Eldorado - Slang Word Detection Model
Training Script
-----------------------------------------------------------
Trains a character-level ML classifier that learns to
distinguish slang words from standard/formal English words.

Why character n-grams?
Slang words are often out-of-dictionary, misspelled on purpose,
or have unusual letter patterns (e.g. "sksksk", "finna", "bussin").
A char n-gram TF-IDF + Logistic Regression model picks up on these
sub-word patterns instead of memorizing exact words, so it can
generalize a bit to new/unseen slang.

Dataset format (CSV):
    word,label
    lit,1
    hello,0
    ...
    label -> 1 = slang, 0 = standard/non-slang

Usage:
    python train_model.py --data slang_dataset_sample.csv --model_out slang_model.pkl
"""

import argparse
import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from sklearn.pipeline import Pipeline
import joblib


def load_dataset(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Dataset not found at: {path}")
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "word" not in df.columns or "label" not in df.columns:
        raise ValueError("CSV must contain 'word' and 'label' columns.")
    df = df.dropna(subset=["word", "label"])
    df["word"] = df["word"].astype(str).str.strip().str.lower()
    df["label"] = df["label"].astype(int)
    df = df.drop_duplicates(subset=["word"])
    return df


def build_pipeline():
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        min_df=1,
        sublinear_tf=True,
    )
    classifier = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
    )
    pipeline = Pipeline([
        ("tfidf", vectorizer),
        ("clf", classifier),
    ])
    return pipeline


def train(data_path, model_out, test_size=0.2, random_state=42):
    print(f"[Eldorado] Loading dataset from {data_path} ...")
    df = load_dataset(data_path)
    n_slang = int(df["label"].sum())
    n_std = int((df["label"] == 0).sum())
    print(f"[Eldorado] Loaded {len(df)} labeled words ({n_slang} slang / {n_std} standard).")

    if n_slang < 5 or n_std < 5:
        print("[Eldorado] WARNING: very small dataset. Add more examples for a real model.")

    X = df["word"]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    pipeline = build_pipeline()
    print("[Eldorado] Training model...")
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    print(f"[Eldorado] Test Accuracy: {acc:.4f}")
    print(classification_report(y_test, y_pred, target_names=["standard", "slang"]))

    joblib.dump(pipeline, model_out)
    print(f"[Eldorado] Model saved to {model_out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train the Eldorado slang detection model.")
    parser.add_argument("--data", default="slang_dataset_sample.csv", help="Path to training CSV dataset")
    parser.add_argument("--model_out", default="slang_model.pkl", help="Output path for trained model")
    parser.add_argument("--test_size", type=float, default=0.2, help="Test split proportion")
    args = parser.parse_args()

    train(args.data, args.model_out, args.test_size)