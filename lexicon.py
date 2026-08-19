"""
lexicon.py
Rule-based signal layer for Lexora — detects abusive/threatening/hate language
directed at government entities. This is the fast, deterministic first pass;
classify.py will combine this with an LLM call for context judgment.

Tiers:
  1 = benign / lawful criticism (not handled here — anything that doesn't
      match tier 2-5 patterns falls through as tier 1 by default)
  2 = abusive / profane language
  3 = hate speech / incitement
  4 = direct threats of violence
  5 = coordinated misinformation (handled separately — needs cross-post
      pattern detection, not a static lexicon; stubbed here)
"""

import re

# ---------------------------------------------------------------------------
# TIER 2 — general abusive/profane terms
# Keep this to generic profanity/insults, not targeted slurs. It's meant to
# catch rude/abusive tone, not identity-based hate (that's tier 3, and that
# list should come from a vetted external dataset — see note at bottom).
# ---------------------------------------------------------------------------
TIER2_ABUSIVE_TERMS = [
    "idiot", "fool", "useless", "shameless", "corrupt scum",
    "worthless", "traitor", "sellout", "liar", "criminal minded",
    # add Hinglish/transliterated variants as you find them, e.g.:
    "bewakoof", "nikamma", "namak haram",
]

# ---------------------------------------------------------------------------
# TIER 3 — hate speech / incitement indicators
# NOTE: Do not hand-roll a slur list here. Load an established, vetted
# dataset instead (see bottom of file for sources). This list only holds
# generic incitement PHRASING patterns, not identity-based terms.
# ---------------------------------------------------------------------------
TIER3_INCITEMENT_PATTERNS = [
    r"\b(destroy|wipe out|eliminate)\s+(all|these)\s+\w+",
    r"\b(these people|that community)\s+(don'?t deserve|should not have)\b",
    r"\bban\s+(all|every)\s+\w+\s+from\b",
]

# ---------------------------------------------------------------------------
# TIER 4 — direct threat patterns (regex, not just keywords — threats are
# usually phrased as intent + violent action + target)
# ---------------------------------------------------------------------------
TIER4_THREAT_PATTERNS = [
    r"\bi will (kill|hurt|attack|burn|bomb)\b",
    r"\bwe will (kill|hurt|attack|burn|bomb)\b",
    r"\b(kill|hang|shoot|burn alive)\s+(him|her|them|modi|the minister|the pm)\b",
    r"\bshould be (killed|hanged|shot|burned)\b",
    r"\bdeath to\b",
    r"\bwe (will|are going to) (burn|torch|attack)\s+(the|his|her|their)\s+(house|office|car)\b",
]

# ---------------------------------------------------------------------------
# Government/target-entity terms — used to confirm WHO the abuse/threat is
# directed at. Text matching tier 2-4 patterns is only actionable if it also
# references a government target; otherwise it's likely unrelated content.
# ---------------------------------------------------------------------------
GOVERNMENT_TARGET_TERMS = [
    "government", "govt", "sarkar", "pm", "prime minister", "modi",
    "minister", "ministry", "parliament", "lok sabha", "rajya sabha",
    "bjp", "congress", "chief minister", "cm", "mla", "mp",
    "police", "collector", "district magistrate", "govt scheme",
    "election commission", "supreme court", "high court",
    "politician", "politicians", "neta", "netas", "leader", "leaders",
    "official", "officials", "cabinet", "administration", "ruling party",
    "opposition", "authorities", "bureaucrat", "bureaucrats",
]


def _compile(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_TIER3_COMPILED = _compile(TIER3_INCITEMENT_PATTERNS)
_TIER4_COMPILED = _compile(TIER4_THREAT_PATTERNS)


def check_lexicon(text: str) -> dict:
    """
    Run the rule-based layer over normalized text.
    Returns the highest tier matched (2-4), the specific terms/patterns
    that triggered it, and whether a government target was referenced.
    Tier 1 (nothing matched) is the default — this function does NOT
    decide tier 1 vs not; classify.py treats "no match" as "defer to LLM".
    """
    text_lower = text.lower()

    matched_tier2 = [t for t in TIER2_ABUSIVE_TERMS if t in text_lower]
    matched_tier3 = [p.pattern for p in _TIER3_COMPILED if p.search(text_lower)]
    matched_tier4 = [p.pattern for p in _TIER4_COMPILED if p.search(text_lower)]

    target_hit = [t for t in GOVERNMENT_TARGET_TERMS if re.search(r"\b" + re.escape(t) + r"\b", text_lower)]

    # Always report which known abusive terms matched, regardless of which
    # tier ends up winning overall — used by classify_local.py to prioritize
    # the actual abusive word in explanations instead of the target word.
    abusive_terms_found = matched_tier2

    if matched_tier4:
        tier = 4
        matches = matched_tier4
    elif matched_tier3:
        tier = 3
        matches = matched_tier3
    elif matched_tier2:
        tier = 2
        matches = matched_tier2
    else:
        tier = None  # no rule-based signal; let the LLM decide
        matches = []

    return {
        "lexicon_tier": tier,
        "matched_terms": matches,
        "government_target_referenced": bool(target_hit),
        "target_terms_found": target_hit,
        "abusive_terms_found": abusive_terms_found,
    }


if __name__ == "__main__":
    # quick manual smoke test
    samples = [
        "This government's policy on fuel prices is a total failure.",
        "The PM is an idiot and a sellout.",
        "We will burn the minister's house down.",
        "I love the new metro station near my house.",
    ]
    for s in samples:
        print(s)
        print(check_lexicon(s))
        print()

# ---------------------------------------------------------------------------
# NOTE on tier 3 (hate speech) coverage:
# Don't hand-type slur lists — they go stale, miss variants, and are easy to
# get legally/ethically wrong. Instead, load a vetted external dataset at
# startup, e.g.:
#   - HASOC (Hate Speech and Offensive Content) shared task datasets
#   - Hate-Alert (IIT Kharagpur) Hindi/English hostile-speech lexicons
#   - Multilingual profanity libraries (e.g. the "better-profanity" or
#     "alt-profanity-check" PyPI packages) as a supplementary layer
# Load whichever you pick into a TIER3_TERMS list here, same pattern as
# TIER2_ABUSIVE_TERMS above.
# ---------------------------------------------------------------------------