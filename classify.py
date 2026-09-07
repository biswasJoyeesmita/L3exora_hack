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
import time
import random
from lexicon import check_lexicon
from dotenv import load_dotenv

load_dotenv()
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL = "gemini-2.0-flash"

# --- Rate limiting / retry config ---
# Free-tier Gemini keys are typically capped at a low requests-per-minute
# limit. We space calls out and retry with backoff on 429s instead of
# letting the whole pipeline die on the first rate-limit hit.
MIN_SECONDS_BETWEEN_CALLS = 1.0   # ~60 req/min for fast live demo responses
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


def build_fallback_justification(tier, target=None, sentiment=None):
    """Describe tone and target when detailed model reasoning is unavailable."""
    target_text = f" toward {target}" if target else " toward a person, group, or institution"
    if tier >= 4:
        return f"The comment expresses a direct or credible threat of physical harm{target_text}, creating a threatening sentiment that requires human review."
    if tier == 3:
        return f"The comment uses dehumanizing, hateful, or violence-encouraging language{target_text}, expressing a harmful and hostile sentiment that requires human review."
    sentiment_text = sentiment or "hostile and disrespectful"
    return f"The comment uses insulting or degrading language{target_text}, expressing a {sentiment_text} sentiment that requires human review."


def _throttle():
    elapsed = time.time() - _last_call_time[0]
    wait = MIN_SECONDS_BETWEEN_CALLS - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_call_time[0] = time.time()

STAGE1_PROMPT = """You are a general-purpose content safety moderator analyzing one comment, post, caption, or reel transcript. Classify the complete content regardless of whether it concerns a government, public figure, creator, brand, group, or private person.

Do NOT judge individual words in isolation. Casual/informal vocabulary (Gen-Z slang like "lit", "sus", "bet", "savage", "cap", "vibe", "lowkey" etc.) is normal everyday language and is NOT inherently a signal of anything. What matters is what the whole sentence is doing — its actual meaning, tone, and intent, read the way a human would read it in context.

Be especially careful with:
- SHORT sentences ("we want X", "X should happen") — these are almost always simple opinions or demands, NOT threats, unless they explicitly describe violence or harm.
- Sarcasm, rhetorical questions, and mockery — read the real intent, not just individual charged words.
- Praise or support for a policy — never flag agreement or positive comments.
- General political/social commentary not actually directed at a specific person or institution.
{context_block}
Classify the sentence into exactly one tier:
1 = benign, supportive, neutral, or mildly critical discussion
2 = clearly negative, distressed, angry, or strongly critical sentiment, including targeted abuse, harassment, bullying, or degrading/disrespectful language
3 = hate speech, dehumanizing attacks on a protected group, or incitement to violence
4 = a direct or credible threat of physical violence

Use tier 2 for clearly negative or distressed sentiment as well as targeted insults, harassment, profanity, mockery, or degrading language. Lawful criticism can still be tier 2 when its emotional tone is strongly negative or distressed; this is a sentiment review tier, not a finding of illegal conduct.
Use tier 3 for protected-group hate, dehumanization, or explicit encouragement of collective violence.
Use tier 4 only for a direct threat of physical harm. Lawful criticism and satire remain tier 1.

Respond ONLY with JSON, no other text:
{{
    "tier": <1-4>,
  "government_target_referenced": <true/false>,
  "target_description": "<who/what is being referenced, or null>",
  "overall_sentiment": "<one short phrase, e.g. 'hostile and threatening', 'casual and neutral', 'critical but lawful', 'supportive'>",
  "confidence": <0.0-1.0>
}}

Sentence: {text}
"""

STAGE2_PROMPT = """This content was flagged as tier {tier} ({sentiment}) toward {target}.

Identify which specific words or phrases are carrying that hostility. Pay special attention to any casual/slang word that is being used here with a harmful sense (not its normal casual meaning) — explain the contextual meaning you're picking up, not just the word itself.

Respond ONLY with JSON, no other text:
{{
  "flagged_spans": [
    {{"phrase": "<exact text>", "why": "<short reason, referencing context not just the word>"}}
  ],
    "justification": "<1-2 sentence explanation of the sentiment, target, and harmful behavior that led to the tier>"
}}

Sentence: {text}
"""

BATCH_PROMPT = """You are a general-purpose content safety moderator analyzing multiple social-media comments about any topic.
Classify each complete comment in context. Do not judge slang or isolated words without considering the whole comment.

Use exactly one tier:
1 = benign, supportive, neutral, or mildly critical discussion
2 = clearly negative, distressed, angry, or strongly critical sentiment, including targeted abuse, harassment, bullying, or degrading/disrespectful language
3 = hate speech, dehumanizing attacks on a protected group, or incitement to violence
4 = a direct or credible threat of physical violence

Use tier 2 for clearly negative or distressed sentiment, or an insult, profanity, mockery, or disrespect aimed at one target. This tier represents content needing sentiment or human review and does not by itself mean the comment is unlawful.
Use tier 3 for calls to revolution, rebellion, riots, taking up arms, collective violence,
dehumanizing attacks on a protected group, or language urging many people to attack or overthrow targets.
Lawful criticism, demands for resignation, and peaceful protest remain tier 1.

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
            response = client.models.generate_content(
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
        if model_tier == 1 and has_negative_sentiment(model_sentiment):
            model_tier = 2
        rule_tier = lex.get("lexicon_tier") or 1
        tier = max(model_tier, rule_tier)
        flagged_terms = lex.get("matched_terms", []) if tier >= 2 else []
        model_spans = result.get("flagged_spans", []) if isinstance(result, dict) else []
        model_terms = [span.get("phrase", "") for span in model_spans if isinstance(span, dict) and span.get("phrase")]
        justification = result.get("justification") if isinstance(result, dict) else None
        if tier >= 2 and not justification:
            justification = build_fallback_justification(
                tier,
                (result.get("target_description") if isinstance(result, dict) else None),
                (result.get("overall_sentiment") if isinstance(result, dict) else None),
            )
        results.append({
            "tier": tier,
            "government_target_referenced": bool(lex.get("government_target_referenced", False)),
            "target_description": (result.get("target_description") if isinstance(result, dict) else None) or ", ".join(lex.get("target_terms_found", [])) or None,
            "overall_sentiment": model_sentiment or ("flagged" if tier >= 2 else "lawful or neutral"),
            "confidence": result.get("confidence") if isinstance(result, dict) else None,
            "flagged_terms": model_terms or flagged_terms,
            "justification": justification,
            "source": "llm_batch",
        })
    return results


def classify(text: str, context: str = None, video_id: str = None) -> dict:
    """
    context: optional short description of where this text appeared —
    e.g. a video title ("Farmer Bill 2026 Explained") or a policy name.
    Helps the LLM read a comment's meaning in light of what it's actually
    reacting to, instead of judging the sentence in a vacuum.

    video_id: accepted for interface parity with classify_local.classify()
    (which uses it to cache a per-video sentiment baseline). Unused here —
    the LLM already gets the title via context_block on every call, so no
    separate caching step is needed for this version.
    """
    # Fast pre-filter: obvious explicit threat patterns (regex) short-circuit
    # straight to tier 4 without needing an LLM call — cheaper and faster.
    lex = check_lexicon(text)
    if lex["lexicon_tier"] == 4:
        return {
            "tier": 4,
            "government_target_referenced": lex["government_target_referenced"],
            "target_description": ", ".join(lex["target_terms_found"]),
            "overall_sentiment": "threatening",
            "confidence": 0.95,
            "flagged_terms": lex["matched_terms"],
            "justification": build_fallback_justification(
                4,
                ", ".join(lex["target_terms_found"]) or None,
                "threatening",
            ),
            "source": "lexicon_prefilter",
        }

    context_block = f"\nThis text is a comment on content titled: \"{context}\" — use this only as background for what the comment is reacting to, do not classify the title itself.\n" if context else ""

    # STAGE 1 — sentence-level sentiment/intent (context, not word lists)
    stage1 = _call_llm(STAGE1_PROMPT.format(text=text, context_block=context_block))

    result = {
        "tier": stage1["tier"] if stage1["tier"] in (1, 2, 3, 4) else 1,
        "government_target_referenced": stage1["government_target_referenced"],
        "target_description": stage1.get("target_description"),
        "overall_sentiment": stage1.get("overall_sentiment"),
        "confidence": stage1.get("confidence"),
        "flagged_terms": [],
        "justification": None,
        "source": "llm_stage1",
    }

    # STAGE 2 — only if Stage 1 says this sentence is actually hostile
    # This tells you WHICH words carried the hostility, with context-aware
    # reasoning instead of a static "bad word" list.
    if stage1["tier"] >= 2:
        stage2 = _call_llm(
            STAGE2_PROMPT.format(
                text=text,
                tier=stage1["tier"],
                sentiment=stage1.get("overall_sentiment", ""),
                target=stage1.get("target_description") or "the referenced person, group, or institution",
            )
        )
        result["flagged_terms"] = [span["phrase"] for span in stage2.get("flagged_spans", [])]
        result["justification"] = stage2.get("justification")
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