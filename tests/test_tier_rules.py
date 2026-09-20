import pathlib
import sys

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from classify import normalize_tier_decision


def test_negative_criticism_without_target_stays_tier_1():
    result = normalize_tier_decision(
        1,
        "critical but lawful",
        {
            "lexicon_tier": None,
            "government_target_referenced": False,
            "abusive_terms_found": [],
        },
    )
    assert result == 1


def test_targeted_abuse_promotes_to_tier_2():
    result = normalize_tier_decision(
        1,
        "hostile and insulting",
        {
            "lexicon_tier": 2,
            "government_target_referenced": True,
            "abusive_terms_found": ["idiot"],
        },
    )
    assert result == 2


def test_direct_threat_stays_tier_4():
    result = normalize_tier_decision(
        1,
        "threatening",
        {
            "lexicon_tier": 4,
            "government_target_referenced": True,
            "abusive_terms_found": [],
        },
    )
    assert result == 4


def test_negative_sentiment_alone_does_not_make_tier_2():
    result = normalize_tier_decision(
        1,
        "angry and frustrated",
        {
            "lexicon_tier": None,
            "government_target_referenced": False,
            "abusive_terms_found": [],
        },
    )
    assert result == 1
