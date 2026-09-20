"""
lexicon.py
Rule-based signal layer for Lexora — detects abusive, threatening, hate,
cybercrime, AI exploit, and illegal activity language directed at ANY target
(individuals, groups, infrastructure, digital systems, or authorities).

Tiers:
  1 = benign / lawful criticism / policy debate (default fallback)
  2 = abusive / profane / degrading language
  3 = hate speech / incitement / synthetic audio/video deception / data breach / illegal scam
  4 = direct threats of violence / cyberattacks / ransomware / zero-days / phishing / MFA bypass / CSAM / voting manipulation
"""

import re

# ---------------------------------------------------------------------------
# TIER 2 — general abusive/profane terms
# ---------------------------------------------------------------------------
TIER2_ABUSIVE_TERMS = [
    "idiot", "fool", "useless", "shameless", "corrupt scum",
    "worthless", "traitor", "sellout", "liar", "criminal minded",
    "bewakoof", "nikamma", "namak haram",
]

# ---------------------------------------------------------------------------
# TIER 3 — hate speech, incitement, synthetic deception, illegal scams & data breaches
# ---------------------------------------------------------------------------
TIER3_INCITEMENT_PATTERNS = [
    r"\b(destroy|wipe out|eliminate)\s+(all|these)\s+\w+",
    r"\b(these people|that community)\s+(don'?t deserve|should not have)\b",
    r"\bban\s+(all|every)\s+\w+\s+from\b",
    r"\b(calls? for|time for|need for)\s+(a\s+)?(revolution|rebellion|uprising)\b",
    r"\b(revolution|rebellion|uprising)\s+(against|of)\b",
    r"\btake (up )?arms\b",
    r"\b(riot|riots|violent unrest|overthrow)\b",
    r"\b(voice cloning|impersonate.*official|fake emergency declaration|synthetic audio depicting|deepfake video showing)\b",
    r"\b(unregistered online real-money betting|illegal financial gambling|intercepting encrypted wireless|leak private user data|untraceable digital key|digital keys|private software)\b",
    r"\b(unauthorized database breach|extraction of private medical|extract.*private.*record)\b",
]

# ---------------------------------------------------------------------------
# TIER 4 — direct threats of violence, cyberattacks, ransomware, zero-days,
# phishing, MFA bypass, CSAM/NCII, and critical infrastructure attacks
# ---------------------------------------------------------------------------
TIER4_THREAT_PATTERNS = [
    r"\b(?:i|we|they|you)\s+(?:will|would|can|could|are going to|am going to|shall)\s+(?:kill|hurt|attack|burn|bomb|shoot|hang)\s+(?:him|her|them|modi|the minister|the pm|someone|anyone|people)\b(?=\s*(?:[.!?,]|$|(?:now|today|tonight|if|because|for)\b))",
    r"\b(?:kill|hang|shoot|burn alive)\s+(?:him|her|them|modi|the minister|the pm|someone|anyone|people)\b(?=\s*(?:[.!?,]|$|(?:now|today|tonight|if|because|for)\b))",
    r"\b(?:should be|must be)\s+(?:killed|hanged|shot|burned)\b",
    r"\bdeath to\b",
    r"\b(?:we|they|i)\s+(?:will|are going to|can|could)\s+(?:burn|torch|attack)\s+(?:the\s+)?(?:[A-Za-z]+['’]s\s+)?(?:house|office|car|home|shop)\b",
    # Cyberattacks, Ransomware, DDoS, Zero-Days, Antivirus Obfuscation, Botnets
    r"\b(compiling ransomware|ransomware source code|ddos attack|denial-of-service|zero-day|vulnerabilities in.*firmware|payload obfuscation|bypass.*antivirus|botnet deployment|credential stuffing)\b",
    # Phishing, Carding, Bank Credential Theft, MFA Bypass
    r"\b(phishing script|harvest bank account|carding guide|unauthorized credit card|bypassing multi-factor authentication|bypass mfa)\b",
    # CSAM / Non-Consensual Imagery, Govt Document Forgery, Voting Tampering, Utility Bypass
    r"\b(synthetic non-consensual|non-consensual intimate|forging official.*document|identity document.*generative|alter.*electronic voting|manipulate.*voting record|bypass public traffic control|utility management system)\b",
]

# ---------------------------------------------------------------------------
# Target-entity terms retained as compatibility metadata for existing clients.
# Moderation applies to abusive or threatening content about any target.
# ---------------------------------------------------------------------------
GOVERNMENT_TARGET_TERMS = [
    "government", "govt", "sarkar", "india", "pm", "prime minister", "modi",
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
    """
    text_lower = text.lower()

    matched_tier2 = [t for t in TIER2_ABUSIVE_TERMS if t in text_lower]
    matched_tier3 = [p.search(text_lower).group(0) for p in _TIER3_COMPILED if p.search(text_lower)]
    matched_tier4 = [p.search(text_lower).group(0) for p in _TIER4_COMPILED if p.search(text_lower)]

    target_hit = [t for t in GOVERNMENT_TARGET_TERMS if re.search(r"\b" + re.escape(t) + r"\b", text_lower)]

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
        tier = None
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