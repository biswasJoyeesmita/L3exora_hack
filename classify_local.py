"""
classify_local.py
Fully local, no-API-key version of the classifier. Uses the model trained
by train_model.py (TF-IDF + Logistic Regression) instead of an LLM call.

Two-stage logic still applies:
  STAGE 1 - the trained model reads the WHOLE sentence and predicts a tier.
            (This is where "sentiment first" happens - the model was trained
            on full sentences, not individual words, so slang words like
            "sus"/"lit"/"savage" only matter in combination with everything
            else in the sentence.)
  STAGE 2 - only if tier >= 2 and a government target is present, pull the
            words/phrases that most influenced that prediction (via the
            model's learned TF-IDF weights) as a lightweight explanation -
            not as rich as an LLM's reasoning, but gives you something to
            show in the demo.

Run train_model.py first to produce tier_model.pkl.
"""

import os
import joblib
from lexicon import check_lexicon

MODEL_PATH = "tier_model.pkl"


def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"{MODEL_PATH} not found. Run `python train_model.py` first."
        )
    return joblib.load(MODEL_PATH)


_pipeline = load_model()
_vectorizer = _pipeline.named_steps["tfidf"]
_clf = _pipeline.named_steps["clf"]


# Very small stopword set just to keep the explanation readable - this is
# NOT a linguistic filter, just noise reduction for a small-data model.
_STOPWORDS = {"is", "are", "the", "a", "an", "and", "of", "to", "this",
              "that", "it", "in", "on", "for", "we", "they", "bro", "tbh",
              "ngl", "lol", "lowkey", "highkey"}


def _top_contributing_terms(text: str, predicted_tier: int, top_n: int = 4) -> list:
    """
    Lightweight explanation: which n-grams in this sentence had the
    strongest learned weight toward the predicted tier's class.
    On this small a dataset, treat this as a rough demo aid, not a
    reliable explanation - it will improve as the dataset grows.
    """
    class_index = list(_clf.classes_).index(predicted_tier)
    coefs = _clf.coef_[class_index] if len(_clf.classes_) > 2 else _clf.coef_[0]

    vec = _vectorizer.transform([text])
    feature_names = _vectorizer.get_feature_names_out()
    nonzero = vec.nonzero()[1]

    scored = [
        (feature_names[i], coefs[i] * vec[0, i])
        for i in nonzero
        if feature_names[i] not in _STOPWORDS and len(feature_names[i]) > 2
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [term for term, score in scored[:top_n] if score > 0]


def classify(text: str) -> dict:
    lex = check_lexicon(text)

    # Fast pre-filter: explicit regex-matched threats short-circuit to tier 4.
    if lex["lexicon_tier"] == 4 and lex["government_target_referenced"]:
        return {
            "tier": 4,
            "government_target_referenced": True,
            "target_description": ", ".join(lex["target_terms_found"]),
            "flagged_terms": lex["matched_terms"],
            "source": "lexicon_prefilter",
        }

    # STAGE 1 - whole-sentence prediction from the trained model
    predicted_tier = int(_pipeline.predict([text])[0])
    government_target = lex["government_target_referenced"] or bool(
        [t for t in lex["target_terms_found"]]
    )

    result = {
        "tier": predicted_tier,
        "government_target_referenced": government_target,
        "target_description": ", ".join(lex["target_terms_found"]) if lex["target_terms_found"] else None,
        "flagged_terms": [],
        "source": "local_model",
    }

    # STAGE 2 - only explain WHICH words drove it if tier looks concerning
    if predicted_tier >= 2 and government_target:
        result["flagged_terms"] = _top_contributing_terms(text, predicted_tier)

    return result


if __name__ == "__main__":
    samples = [
        "ngl this govt scheme is lowkey a mess, the vibe is just chaos",
        "bro the PM is sus af, this whole scheme is a scam and should be shut down",
        "these politicians are savage, we should burn their houses down deadass",
        "lol this weather is so sus today, might rain",
        "the minister is a straight up traitor, death to all of them",
    ]

    lines = []
    for s in samples:
        result = classify(s)
        lines.append(f"TEXT: {s}")
        lines.append(str(result))
        lines.append("")  # blank line between entries

    output_text = "\n".join(lines)
    print(output_text)  # still shows in terminal

    with open("output.txt", "w", encoding="utf-8") as f:
        f.write(output_text)
    print(f"\nResults written to output.txt")