"""
classify.py
Two-stage classifier for Lexora.

STAGE 1 — sentence-level sentiment/intent.
  We do NOT flag words in isolation ("lit", "sus", "bet", "savage" etc. are
  normal Gen-Z vocabulary, not slurs). We first ask: what is this sentence
actually doing? Is it hostile, threatening, or disrespectful, or is it just
casual/normal talk that happens to use informal words?

STAGE 2 — only runs if Stage 1 flags the sentence as hostile/threatening.
  Once we know the sentence reads as hostile, we go back and identify which
  specific words/phrases are carrying that hostility, including cases where
  an ordinary casual word ("savage", "sus", "cap") is being used with a
harmful sense in THIS context.

This mirrors how humans actually read tone: context sets meaning, not a
word list. Combine this with lexicon.py's fast regex tier-4 threat check
(obvious direct threats) as a pre-filter. Target matching is descriptive only.
"""

import json
import os
import re
import time
import random
from lexicon import check_lexicon
from dotenv import load_dotenv

load_dotenv()
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

MODEL = "gemini-3.6-flash"

# Client is created lazily, on first actual use — NOT at import time. If
# GEMINI_API_KEY is missing/invalid, importing this file won't crash the
# whole app; the failure surfaces only when a call is attempted, which lets
# classify_router.py catch it and fail over to the local model instead of
# the entire server refusing to start.
_client = None


def _get_client():
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=api_key)
    return _client

# --- Rate limiting / retry config ---
# Free-tier Gemini keys are typically capped at a low requests-per-minute
# limit. We space calls out and retry with backoff on 429s instead of
# letting the whole pipeline die on the first rate-limit hit.
MIN_SECONDS_BETWEEN_CALLS = 0.1   # Fast batch execution with retry fallback on 429
MAX_RETRIES = 2
_last_call_time = [0.0]
NEGATIVE_SENTIMENT_MARKERS = (
    "angry", "anger", " outrage", "outrage", "fear", "afraid", "grief", "grieving",
    "sad", "sorrow", "distress", "distressed", "hostile", "negative", "critical",
    "frustrat", "concern", "distrust", "disgust", "resent", "protest", "harsh",
    "threat", "violent", "abusive", "hate", "hopeless", "panic",
)


def has_negative_sentiment(sentiment):
    """Return true for clearly negative or distressed model sentiment labels."""
    value = str(sentiment or "").lower()
    return any(marker in value for marker in NEGATIVE_SENTIMENT_MARKERS)


def normalize_tier_decision(model_tier, sentiment, lex_result=None):
    """Promote only explicit target-specific hostility; never upgrade purely negative sentiment alone."""
    lex_result = lex_result or {}
    try:
        normalized = int(model_tier)
    except (TypeError, ValueError):
        normalized = 1
    if normalized not in (1, 2, 3, 4):
        normalized = 1

    rule_tier = lex_result.get("lexicon_tier") or 1
    if rule_tier > normalized:
        return int(rule_tier)
    if normalized != 1:
        return normalized
    if not has_negative_sentiment(sentiment):
        return 1
    if lex_result.get("government_target_referenced") or lex_result.get("abusive_terms_found"):
        return 2
    return 1


def build_structured_justification(tier, target=None, sentiment=None, triggers=None, explanation=None):
    """
    Generates a clean, standardized, multi-field structured justification for flagged items.
    
    Structure:
    • Severity: Tier X (<Tier Label>)
    • Target: <Target description or 'General / Unspecified'>
    • Triggers: <Matched terms / patterns>
    • Intent: <Overall sentiment / intent>
    • Explanation: <Detailed contextual reasoning>
    """
    tier_labels = {
        4: "Tier 4 (Critical Threat / Prohibited Exploit)",
        3: "Tier 3 (Incitement / Cyber & AI Deception)",
        2: "Tier 2 (Abusive / Disrespectful)",
        1: "Tier 1 (Lawful / Neutral)",
    }
    severity_str = tier_labels.get(tier, f"Tier {tier}")
    target_str = target if target else "General / Unspecified"
    
    if isinstance(triggers, list) and triggers:
        cleaned_triggers = []
        for t in triggers:
            clean_t = re.sub(r'\\b|\^|\$|\(\?:|\)|\(|\)', '', str(t)).replace('|', ', ').strip()
            if clean_t and clean_t not in cleaned_triggers:
                cleaned_triggers.append(clean_t)
        triggers_str = ", ".join(cleaned_triggers[:5]) if cleaned_triggers else "Contextual Signal"
    elif isinstance(triggers, str) and triggers.strip():
        triggers_str = re.sub(r'\\b|\^|\$|\(\?:|\)|\(|\)', '', triggers.strip()).replace('|', ', ')
    else:
        triggers_str = "Contextual Pattern / Keyword Signal"
        
    intent_str = sentiment or ("Hostile / Prohibited" if tier >= 2 else "Neutral")
    
    if not explanation or not explanation.strip():
        if tier >= 4:
            explanation = "Content involves severe prohibited activities, cyberattacks, ransomware, or direct threats requiring immediate human review."
        elif tier == 3:
            explanation = "Content contains incitement to violence, deepfake deception, database breaches, or illegal scam activities requiring review."
        elif tier == 2:
            explanation = "Content uses targeted insults, profanity, or degrading language requiring review."
        else:
            explanation = "Content is classified as lawful criticism or benign discussion."
    else:
        explanation = explanation.strip()

    return (
        f"• Severity: {severity_str}\n"
        f"• Target: {target_str}\n"
        f"• Triggers: {triggers_str}\n"
        f"• Intent: {intent_str}\n"
        f"• Explanation: {explanation}"
    )


def build_fallback_justification(tier, target=None, sentiment=None, triggers=None):
    """Backwards-compatible wrapper returning structured justification."""
    return build_structured_justification(tier, target=target, sentiment=sentiment, triggers=triggers)


def _throttle():
    elapsed = time.time() - _last_call_time[0]
    wait = MIN_SECONDS_BETWEEN_CALLS - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_call_time[0] = time.time()

STAGE1_PROMPT = """You are a general-purpose content safety moderator analyzing one comment, post, caption, query, or transcript. Classify the complete content regardless of whether it concerns a government official, private individual, organization, public infrastructure, digital network, or election system.

Do NOT judge individual words in isolation. Casual/informal vocabulary (Gen-Z slang like "lit", "sus", "bet", "savage", "cap", "vibe", "lowkey" etc.) is normal everyday language and is NOT inherently a signal of anything. What matters is what the whole sentence is doing — its actual meaning, tone, and intent, read the way a human would read it in context.

Be especially careful with:
- SHORT sentences or HASHTAGS ("#ai_ethics", "we want X", "X should happen") — these are almost always simple opinions, policy debates, or demands, NOT threats, unless they explicitly describe cyberattacks, violence, or illegal exploits.
- Sarcasm, rhetorical questions, and mockery — read the real intent, not just individual charged words.
- Policy discussion, technological debate, news, or general public commentary — keep these Tier 1 unless harmful/prohibited content is present.
{context_block}
Classify the content into exactly one tier:
1 = benign, supportive, neutral, policy debate, or lawful criticism with no abusive or prohibited content
2 = targeted abuse, harassment, bullying, profanity, or degrading language directed at a specific person, group, or institution
3 = hate speech, dehumanizing attacks, incitement to violence, fake emergency audio, voice cloning impersonation, illegal database breaches, carding guides, or illegal gambling scam apps
4 = direct/credible physical threats, ransomware source code, DDoS attacks, zero-day firmware exploits, phishing templates, MFA bypass, non-consensual synthetic imagery (CSAM/NCII), identity document forgery, or voting record manipulation

Respond ONLY with JSON, no other text:
{{
  "tier": <1-4>,
  "government_target_referenced": <true/false>,
  "target_description": "<who/what is being referenced, or null>",
  "overall_sentiment": "<one short phrase, e.g. 'prohibited exploit', 'hostile and threatening', 'casual and neutral', 'critical but lawful', 'supportive'>",
  "confidence": <0.0-1.0>
}}

Sentence: {text}
"""

STAGE2_PROMPT = """This content was flagged as tier {tier} ({sentiment}) toward {target}.

Identify which specific words or phrases are carrying that hostility or prohibited exploit behavior. Pay special attention to any casual/slang word that is being used here with a harmful sense — explain the contextual meaning you're picking up.

Respond ONLY with JSON, no other text:
{{
  "flagged_spans": [
    {{"phrase": "<exact text>", "why": "<short reason, referencing context not just the word>"}}
  ],
  "justification": "<1-2 sentence explanation of the sentiment, target, and harmful behavior that led to the tier>"
}}

Sentence: {text}
"""

BATCH_PROMPT = """You are a general-purpose content safety moderator analyzing multiple social-media comments, queries, or posts about any topic.
Classify each complete item in context regardless of whether it concerns a government figure, private person, digital asset, or infrastructure.

Use exactly one tier:
1 = benign, supportive, neutral, policy debate (e.g. #ai_ethics, #dataprivacy), or lawful criticism
2 = targeted abuse, harassment, bullying, profanity, or degrading language directed at a person, group, or institution
3 = hate speech, incitement to violence, fake emergency audio, voice cloning impersonation, unauthorized database breaches, credit card carding guides, or illegal financial gambling apps
4 = direct physical threats, ransomware source code compilation, DDoS attacks, zero-day firmware exploits, phishing templates, MFA bypass, non-consensual synthetic imagery (NCII/CSAM), identity document forgery, or electronic voting record manipulation

Return ONLY a JSON array with exactly one object for every input comment, in the same order.
Each object must contain: tier (1-4), overall_sentiment, target_description, confidence,
flagged_spans (array of exact phrases), and justification (one concise, specific reason).

COMMENTS:
{comments}
"""

def _call_llm(prompt: str) -> dict:
    for attempt in range(MAX_RETRIES):
        _throttle()
        try:
            response = _get_client().models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                )
            )
            raw = response.text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                start, end = raw.find("{"), raw.rfind("}")
                if start != -1 and end != -1:
                    return json.loads(raw[start:end + 1])
                raise
        except genai_errors.ClientError as e:
            # 429 = rate limited, 503 = overloaded. Both are worth retrying.
            # Anything else (bad request, auth error, etc.) re-raises immediately —
            # retrying won't fix those.
            is_retryable = getattr(e, "code", None) in (429, 503)
            if not is_retryable or attempt == MAX_RETRIES - 1:
                raise
            backoff = (2 ** attempt) + random.uniform(0, 1)
            print(f"  [rate-limited, retrying in {backoff:.1f}s — attempt {attempt + 1}/{MAX_RETRIES}]")
            time.sleep(backoff)
    # Unreachable: the loop above always returns or raises before falling
    # through (the last attempt's except block re-raises unconditionally).
    # This satisfies the type checker's requirement that the function has
    # an explicit exit on every path.
    raise RuntimeError("_call_llm exhausted retries without returning or raising")


def classify_batch(items: list[dict]) -> list[dict]:
    """Classify a small batch in one Gemini request to keep report generation fast."""
    if not items:
        return []

    formatted = "\n\n".join(
        f"[{index}] Video context: {item.get('context') or 'none'}\nComment: {item.get('text', '')}"
        for index, item in enumerate(items, 1)
    )
    raw_results = _call_llm(BATCH_PROMPT.format(comments=formatted))
    if not isinstance(raw_results, list) or len(raw_results) != len(items):
        raise ValueError("Batch classifier returned an unexpected number of results")

    results = []
    for item, result in zip(items, raw_results):
        lex = check_lexicon(item.get("text", ""))
        model_tier = int(result.get("tier", 1)) if isinstance(result, dict) else 1
        model_tier = model_tier if model_tier in (1, 2, 3, 4) else 1
        model_sentiment = result.get("overall_sentiment") if isinstance(result, dict) else None
        model_tier = normalize_tier_decision(model_tier, model_sentiment, lex)
        rule_tier = lex.get("lexicon_tier") or 1
        tier = max(model_tier, rule_tier)
        flagged_terms = lex.get("matched_terms", []) if tier >= 2 else []
        model_spans = result.get("flagged_spans", []) if isinstance(result, dict) else []
        model_terms = [span.get("phrase", "") for span in model_spans if isinstance(span, dict) and span.get("phrase")]
        target_desc = (result.get("target_description") if isinstance(result, dict) else None) or ", ".join(lex.get("target_terms_found", [])) or None
        sentiment_desc = model_sentiment or ("flagged" if tier >= 2 else "lawful or neutral")
        all_terms = model_terms or flagged_terms or lex.get("matched_terms", [])
        justification_raw = result.get("justification") if isinstance(result, dict) else None
        
        justification = build_structured_justification(
            tier,
            target=target_desc,
            sentiment=sentiment_desc,
            triggers=all_terms,
            explanation=justification_raw
        ) if tier >= 2 else None

        results.append({
            "tier": tier,
            "government_target_referenced": bool(lex.get("government_target_referenced", False)),
            "target_description": target_desc,
            "overall_sentiment": sentiment_desc,
            "confidence": result.get("confidence") if isinstance(result, dict) else None,
            "flagged_terms": all_terms,
            "justification": justification,
            "source": "llm_batch",
        })
    return results


def classify(text: str, context: str = None, video_id: str = None) -> dict:
    """
    context: optional short description of where this text appeared —
    e.g. a video title ("Farmer Bill 2026 Explained") or a policy name.
    """
    lex = check_lexicon(text)
    if lex["lexicon_tier"] and lex["lexicon_tier"] >= 3:
        tier_num = lex["lexicon_tier"]
        target_desc = ", ".join(lex["target_terms_found"]) if lex["target_terms_found"] else None
        flagged_terms = lex["matched_terms"]
        justification = build_structured_justification(
            tier_num,
            target=target_desc,
            sentiment="prohibited activity / threat",
            triggers=flagged_terms,
            explanation=f"Content matched rule-based signal for prohibited exploit: {', '.join(flagged_terms[:3])}."
        )
        return {
            "tier": tier_num,
            "government_target_referenced": lex["government_target_referenced"],
            "target_description": target_desc,
            "overall_sentiment": "prohibited activity",
            "confidence": 0.95,
            "flagged_terms": flagged_terms,
            "justification": justification,
            "source": "lexicon_prefilter",
        }

    context_block = f"\nThis text is a comment on content titled: \"{context}\" — use this only as background for what the comment is reacting to, do not classify the title itself.\n" if context else ""

    # STAGE 1 — sentence-level sentiment/intent (context, not word lists)
    stage1 = _call_llm(STAGE1_PROMPT.format(text=text, context_block=context_block))

    stage1_tier = stage1["tier"] if stage1["tier"] in (1, 2, 3, 4) else 1
    tier = normalize_tier_decision(stage1_tier, stage1.get("overall_sentiment"), lex)
    
    result = {
        "tier": tier,
        "government_target_referenced": stage1["government_target_referenced"],
        "target_description": stage1.get("target_description"),
        "overall_sentiment": stage1.get("overall_sentiment"),
        "confidence": stage1.get("confidence"),
        "flagged_terms": [],
        "justification": None,
        "source": "llm_stage1",
    }

    if result["tier"] >= 2:
        stage2 = _call_llm(
            STAGE2_PROMPT.format(
                text=text,
                tier=stage1["tier"],
                sentiment=stage1.get("overall_sentiment", ""),
                target=stage1.get("target_description") or "the referenced person, group, or institution",
            )
        )
        flagged_spans = [span["phrase"] for span in stage2.get("flagged_spans", [])]
        raw_explanation = stage2.get("justification")
        
        result["flagged_terms"] = flagged_spans
        result["justification"] = build_structured_justification(
            tier,
            target=result.get("target_description"),
            sentiment=result.get("overall_sentiment"),
            triggers=flagged_spans or lex.get("matched_terms", []),
            explanation=raw_explanation
        )
        result["source"] = "llm_stage1+2"

    return result


if __name__ == "__main__":
    samples = [
        ("ngl this govt scheme is lowkey a mess, the vibe is just chaos", None),
        ("bro the PM is sus af, this whole scheme is a scam and should be shut down", None),
        ("caa should be implemented.", "CAA and NRC Explained"),
        ("We want nrc", "Shaheen Bagh Women Talk About CAA, NRC Protest"),
    ]
    for text, ctx in samples:
        print("TEXT:", text)
        print(json.dumps(classify(text, context=ctx), indent=2))
        print()