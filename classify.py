"""
classify.py
Two-stage classifier for Lexora.

STAGE 1 — sentence-level sentiment/intent.
  We do NOT flag words in isolation ("lit", "sus", "bet", "savage" etc. are
  normal Gen-Z vocabulary, not slurs). We first ask: what is this sentence
  actually doing? Is it hostile, threatening, or disrespectful toward a
  government target — or is it just casual/normal talk that happens to use
  informal words?

STAGE 2 — only runs if Stage 1 flags the sentence as hostile/threatening.
  Once we know the sentence reads as hostile, we go back and identify which
  specific words/phrases are carrying that hostility, including cases where
  an ordinary casual word ("savage", "sus", "cap") is being used with a
  harmful sense in THIS context (e.g. "sus" used to imply the government is
  criminally corrupt vs. "sus" used to describe suspicious weather).

This mirrors how humans actually read tone: context sets meaning, not a
word list. Combine this with lexicon.py's fast regex tier-4 threat check
(obvious direct threats) as a pre-filter, and government-target matching
to confirm relevance.
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
MODEL = "gemini-3.5-flash-lite"

# --- Rate limiting / retry config ---
# Free-tier Gemini keys are typically capped at a low requests-per-minute
# limit. We space calls out and retry with backoff on 429s instead of
# letting the whole pipeline die on the first rate-limit hit.
MIN_SECONDS_BETWEEN_CALLS = 1.0   # ~60 req/min for fast live demo responses
MAX_RETRIES = 2
_last_call_time = [0.0]


def _throttle():
    elapsed = time.time() - _last_call_time[0]
    wait = MIN_SECONDS_BETWEEN_CALLS - elapsed
    if wait > 0:
        time.sleep(wait)
    _last_call_time[0] = time.time()

STAGE1_PROMPT = """You are analyzing a single sentence for its overall sentiment and intent toward the Government of India (or a government official/institution), if any government target is present at all.

Do NOT judge individual words in isolation. Casual/informal vocabulary (Gen-Z slang like "lit", "sus", "bet", "savage", "cap", "vibe", "lowkey" etc.) is normal everyday language and is NOT inherently a signal of anything. What matters is what the whole sentence is doing — its actual meaning, tone, and intent, read the way a human would read it in context.

Be especially careful with:
- SHORT sentences ("we want X", "X should happen") — these are almost always simple opinions or demands, NOT threats, unless they explicitly describe violence or harm.
- Sarcasm, rhetorical questions, and mockery — read the real intent, not just individual charged words.
- Praise or support for a policy — never flag agreement or positive comments.
- General political/social commentary not actually directed at a specific person or institution.
{context_block}
Classify the sentence into exactly one tier:
1 = benign / lawful criticism (including harsh but legal criticism of policy), support/praise, or unrelated/normal talk
2 = abusive or disrespectful language directed at a government target
3 = hate speech, dehumanizing group attacks, or incitement to widespread unrest/violence against a government target
4 = direct threat of violence against a government target
5 = likely coordinated misinformation about government

Use tier 2 for an insult, profanity, mockery, or disrespect aimed at one target.
Use tier 3 for calls to revolution, rebellion, riots, taking up arms, collective violence,
dehumanizing attacks on a protected group, or language urging many people to attack or overthrow targets.
Lawful criticism, demands for resignation, and peaceful protest remain tier 1.

Respond ONLY with JSON, no other text:
{{
  "tier": <1-5>,
  "government_target_referenced": <true/false>,
  "target_description": "<who/what is being referenced, or null>",
  "overall_sentiment": "<one short phrase, e.g. 'hostile and threatening', 'casual and neutral', 'critical but lawful', 'supportive'>",
  "confidence": <0.0-1.0>
}}

Sentence: {text}
"""

STAGE2_PROMPT = """This sentence was flagged as tier {tier} ({sentiment}) toward a government target.

Identify which specific words or phrases are carrying that hostility. Pay special attention to any casual/slang word that is being used here with a harmful sense (not its normal casual meaning) — explain the contextual meaning you're picking up, not just the word itself.

Respond ONLY with JSON, no other text:
{{
  "flagged_spans": [
    {{"phrase": "<exact text>", "why": "<short reason, referencing context not just the word>"}}
  ],
  "justification": "<1-2 sentence overall explanation for the tier assigned>"
}}

Sentence: {text}
"""

BATCH_PROMPT = """You are analyzing multiple YouTube comments about government policy or public affairs.
Classify each complete comment in context. Do not judge slang or isolated words without considering the whole comment.

Use exactly one tier:
1 = benign / lawful criticism, support, praise, or unrelated talk
2 = abusive or disrespectful language directed at a government target
3 = hate speech, dehumanizing group attacks, or incitement to widespread unrest/violence against a government target
4 = direct threat of violence against a government target
5 = likely coordinated misinformation about government

Use tier 2 for an insult, profanity, mockery, or disrespect aimed at one target.
Use tier 3 for calls to revolution, rebellion, riots, taking up arms, collective violence,
dehumanizing attacks on a protected group, or language urging many people to attack or overthrow targets.
Lawful criticism, demands for resignation, and peaceful protest remain tier 1.

Return ONLY a JSON array of tier numbers with exactly one number for every input comment, in the same order.
Example for three comments: [1, 2, 1]

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
        model_tier = int(result) if int(result) in (1, 2, 3, 4, 5) else 1
        rule_tier = lex.get("lexicon_tier") or 1
        tier = max(model_tier, rule_tier) if lex.get("government_target_referenced") else model_tier
        flagged_terms = lex.get("matched_terms", []) if tier >= 2 else []
        justification = None
        if tier >= 2:
            justification = (
                "Model identified abusive or disrespectful language toward a government target."
                if tier == 2 else
                "Model identified hate speech or incitement toward a government target."
                if tier == 3 else
                "Model identified a direct threat toward a government target."
                if tier == 4 else
                "Model identified likely coordinated misinformation about government."
            )
        results.append({
            "tier": tier,
            "government_target_referenced": bool(lex.get("government_target_referenced", False)),
            "target_description": ", ".join(lex.get("target_terms_found", [])) or None,
            "overall_sentiment": "flagged by batch model" if tier >= 2 else "lawful or neutral",
            "confidence": None,
            "flagged_terms": flagged_terms,
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
    if lex["lexicon_tier"] == 4 and lex["government_target_referenced"]:
        return {
            "tier": 4,
            "government_target_referenced": True,
            "target_description": ", ".join(lex["target_terms_found"]),
            "overall_sentiment": "explicit threat (rule-based match)",
            "confidence": 0.95,
            "flagged_terms": lex["matched_terms"],
            "justification": "Matched an explicit threat pattern via lexicon, confirmed by rule-based pre-filter.",
            "source": "lexicon_prefilter",
        }

    context_block = f"\nThis text is a comment on content titled: \"{context}\" — use this only as background for what the comment is reacting to, do not classify the title itself.\n" if context else ""

    # STAGE 1 — sentence-level sentiment/intent (context, not word lists)
    stage1 = _call_llm(STAGE1_PROMPT.format(text=text, context_block=context_block))

    result = {
        "tier": stage1["tier"],
        "government_target_referenced": stage1["government_target_referenced"],
        "target_description": stage1.get("target_description"),
        "overall_sentiment": stage1.get("overall_sentiment"),
        "confidence": stage1.get("confidence"),
        "flagged_terms": [],
        "justification": None,
        "source": "llm_stage1",
    }

    # STAGE 2 — only if Stage 1 says this sentence is actually hostile
    # AND it's actually about a government target. This is the step that
    # tells you WHICH words carried the hostility, with context-aware
    # reasoning instead of a static "bad word" list.
    if stage1["tier"] >= 2 and stage1["government_target_referenced"]:
        stage2 = _call_llm(
            STAGE2_PROMPT.format(text=text, tier=stage1["tier"], sentiment=stage1.get("overall_sentiment", ""))
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