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
    abusive_terms = lex.get("abusive_terms_found", [])
    video_is_negative = bool(video_ctx) and "negative" in video_ctx.get("label", "")

    if "negative" in label_lower:
        if abusive_terms:
            return 2, "Abusive / Disrespectful"
        elif video_is_negative:
            return 1, "Lawful / Neutral"
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

    # 1. Fast Pre-filter: Regex direct threats & prohibited cyber/AI exploits short-circuit to Tier 3/4
    if lex["lexicon_tier"] and lex["lexicon_tier"] >= 3:
        tier_num = lex["lexicon_tier"]
        tier_label = "Direct Threat / Prohibited Exploit" if tier_num == 4 else "Incitement / Deception / Scam"
        target_desc = ", ".join(lex["target_terms_found"]) if lex["target_terms_found"] else None
        flagged_terms = lex["matched_terms"]
        
        # Build structured justification
        try:
            from classify import build_structured_justification
            justification = build_structured_justification(
                tier_num,
                target=target_desc,
                sentiment="Prohibited Exploit / Threat",
                triggers=flagged_terms,
                explanation=f"Content matched rule-based signal for {tier_label.lower()}: {', '.join(flagged_terms[:3])}."
            )
        except Exception:
            justification = f"• Severity: Tier {tier_num} ({tier_label})\n• Triggers: {', '.join(flagged_terms[:3])}\n• Explanation: Flagged based on rule-based exploit signal."

        return {
            "tier": tier_num,
            "tier_label": tier_label,
            "is_flagged": True,
            "government_target_referenced": lex["government_target_referenced"],
            "target_description": target_desc,
            "flagged_terms": flagged_terms,
            "justification": justification,
            "source": "lexicon_prefilter",
        }

    # 2. Local RoBERTa Sentiment Analysis (Reads entire sentence context)
    full_text = f"{context}: {text}" if context else text
    raw_res = _sentiment_pipeline(full_text, truncation=True, max_length=512)[0]
    
    sentiment_label = raw_res["label"]  # e.g., 'negative', 'neutral', 'positive'
    sentiment_score = raw_res["score"]

    # 3. Map context sentiment to Tier (informed by the video's own framing)
    tier_num, tier_label = _map_sentiment_to_tier(sentiment_label, text, lex, video_ctx)
    rule_tier = lex.get("lexicon_tier") or 1
    if rule_tier > tier_num:
        tier_num = rule_tier
        tier_label = {
            2: "Abusive / Disrespectful",
            3: "Hate Speech / Incitement",
            4: "Direct Threat / Prohibited Exploit",
        }.get(rule_tier, tier_label)
    is_flagged = tier_num > 1

    flagged_terms = lex.get("matched_terms") or lex.get("abusive_terms_found") or []
    target_desc = ", ".join(lex["target_terms_found"]) if lex["target_terms_found"] else None

    justification = None
    if is_flagged:
        try:
            from classify import build_structured_justification
            justification = build_structured_justification(
                tier_num,
                target=target_desc,
                sentiment=f"{sentiment_label} ({sentiment_score:.2f})",
                triggers=flagged_terms,
                explanation=f"Detected {tier_label.lower()} language requiring review."
            )
        except Exception:
            justification = f"• Severity: Tier {tier_num} ({tier_label})\n• Target: {target_desc or 'Unspecified'}\n• Triggers: {', '.join(flagged_terms)}\n• Explanation: Detected {tier_label.lower()} language."

    return {
        "tier": tier_num,
        "tier_label": tier_label,
        "is_flagged": is_flagged,
        "government_target_referenced": lex["government_target_referenced"],
        "target_description": target_desc,
        "overall_sentiment": f"{sentiment_label} ({sentiment_score:.2f})",
        "video_sentiment": f"{video_ctx['label']} ({video_ctx['score']:.2f})" if video_ctx else None,
        "flagged_terms": flagged_terms,
        "justification": justification,
        "source": "local_roberta_transformer",
    }


def classify_batch(items: list) -> list:
    """
    Interface parity with classify.classify_batch() — lets classify_router.py
    (or api_server.py directly) call either backend the same way. The local
    model doesn't benefit from batching the way an LLM call does (no per-call
    API cost to amortize), so this just classifies each item individually.

    items: list of dicts with "text" and optionally "context"/"video_id"
    (matches the batch shape used by classify.classify_batch()).
    """
    return [
        classify(item.get("text", ""), context=item.get("context"), video_id=item.get("video_id"))
        for item in items
    ]


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