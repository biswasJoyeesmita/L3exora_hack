"""
classify_local.py
Fully local, zero-API-key version using Hugging Face RoBERTa Sentiment Model.
Processes full sentence context, irony, and sentiment locally.
"""

import os
from transformers import pipeline
from lexicon import check_lexicon

# Load Hugging Face RoBERTa Sentiment Model locally (downloads automatically on first run)
print("Loading local Hugging Face sentiment model...")
_sentiment_pipeline = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest"
)


def _map_sentiment_to_tier(label: str, text: str, lex: dict, video_ctx: dict = None) -> tuple:
    """
    Maps RoBERTa sentiment output + Lexicon signals to Lexora Tiers:
    - positive / neutral -> Tier 1 (Lawful / Neutral)
    - negative + abusive terms -> Tier 2 (Abusive / Disrespectful)
    - negative + target, but no abusive terms, AND the video itself is
      already framed negatively (e.g. protest coverage) -> Tier 1: this is
      just agreement with the video's own framing, not disrespect.
    - negative + target, no abusive terms, video is neutral/positive ->
      Tier 2: unprompted hostility, worth a human look.
    """
    label_lower = label.lower()
    has_target = lex["government_target_referenced"]
    abusive_terms = lex.get("abusive_terms_found", [])
    video_is_negative = bool(video_ctx) and "negative" in video_ctx.get("label", "")

    if "negative" in label_lower:
        if has_target and abusive_terms:
            return 2, "Abusive / Disrespectful"
        elif has_target and video_is_negative:
            return 1, "Lawful / Neutral"
        elif has_target:
            return 2, "Critical / Disrespectful"
        else:
            return 1, "Lawful / Neutral"
    else:
        # Neutral or Positive sentiment = Tier 1 (Lawful)
        return 1, "Lawful / Neutral"


_video_sentiment_cache = {}


def classify_video_context(video_id: str, video_title: str) -> dict:
    """
    Classifies the sentiment/framing of the VIDEO ITSELF (title), once per
    video, and caches it. This gives comment-level classification a baseline
    to react against — e.g. a blunt comment agreeing with an already-critical
    video reads differently than the same comment on a neutral/supportive one.
    """
    if video_id in _video_sentiment_cache:
        return _video_sentiment_cache[video_id]

    raw_res = _sentiment_pipeline(video_title, truncation=True, max_length=512)[0]
    result = {"label": raw_res["label"].lower(), "score": raw_res["score"]}
    _video_sentiment_cache[video_id] = result
    return result


def classify(text: str, context: str = None, video_id: str = None) -> dict:
    lex = check_lexicon(text)

    video_ctx = None
    if video_id and context:
        video_ctx = classify_video_context(video_id, context)

    # 1. Fast Pre-filter: Regex direct threats short-circuit to Tier 4
    if lex["lexicon_tier"] == 4 and lex["government_target_referenced"]:
        return {
            "tier": 4,
            "tier_label": "Direct Threat",
            "is_flagged": True,
            "government_target_referenced": True,
            "target_description": ", ".join(lex["target_terms_found"]),
            "flagged_terms": lex["matched_terms"],
            "source": "lexicon_prefilter",
        }

    # 2. Local RoBERTa Sentiment Analysis (Reads entire sentence context)
    full_text = f"{context}: {text}" if context else text
    raw_res = _sentiment_pipeline(full_text, truncation=True, max_length=512)[0]
    
    sentiment_label = raw_res["label"]  # e.g., 'negative', 'neutral', 'positive'
    sentiment_score = raw_res["score"]

    # 3. Map context sentiment to Tier (informed by the video's own framing)
    tier_num, tier_label = _map_sentiment_to_tier(sentiment_label, text, lex, video_ctx)
    is_flagged = tier_num > 1

    return {
        "tier": tier_num,
        "tier_label": tier_label,
        "is_flagged": is_flagged,
        "government_target_referenced": lex["government_target_referenced"],
        "target_description": ", ".join(lex["target_terms_found"]) if lex["target_terms_found"] else None,
        "overall_sentiment": f"{sentiment_label} ({sentiment_score:.2f})",
        "video_sentiment": f"{video_ctx['label']} ({video_ctx['score']:.2f})" if video_ctx else None,
        "flagged_terms": lex.get("abusive_terms_found", []),
        "source": "local_roberta_transformer",
    }


if __name__ == "__main__":
    samples = [
        "ngl this govt scheme is lowkey a mess, the vibe is just chaos",
        "bro the PM is sus af, this whole scheme is a scam and should be shut down",
        "lol this weather is so sus today, might rain",
        "the minister is a straight up traitor, death to all of them",
    ]

    for s in samples:
        res = classify(s)
        print(f"TEXT: {s}")
        print(f"RESULT: {res}\n")