"""
classify_router.py
Single entry point for classification. api_server.py imports THIS, not
classify.py or classify_local.py directly, so the local Hugging Face model
is an ACTUAL fallback — not just a file that exists but is never called.

One shared, thread-safe flag decides Gemini vs. local for every request —
not a per-request decision — so concurrent users don't each independently
discover Gemini is down and pile on retries against an exhausted quota.
"""

import threading
import time

import classify as _gemini
import classify_local as _local

COOLDOWN_SECONDS = 5 * 60  # after a failure, wait this long before retrying Gemini

_lock = threading.Lock()
_state = {"gemini_available": True, "tripped_at": None}


def _trip_to_local(reason: str) -> None:
    with _lock:
        if _state["gemini_available"]:
            print(f"  [FAILOVER] Gemini unavailable ({reason}) — switching to local model.")
        _state["gemini_available"] = False
        _state["tripped_at"] = time.time()


def _should_try_gemini() -> bool:
    with _lock:
        if _state["gemini_available"]:
            return True
        if _state["tripped_at"] is not None and time.time() - _state["tripped_at"] >= COOLDOWN_SECONDS:
            return True
        return False


def _mark_recovered() -> None:
    with _lock:
        if not _state["gemini_available"]:
            print("  [RECOVERY] Gemini responded again — switching back from local model.")
        _state["gemini_available"] = True
        _state["tripped_at"] = None


def classify_batch(items: list) -> list:
    if not items:
        return []

    if _should_try_gemini():
        try:
            results = _gemini.classify_batch(items)
            _mark_recovered()
            for r in results:
                r["degraded_mode"] = False
            return results
        except Exception as e:
            _trip_to_local(str(e))

    results = _local.classify_batch(items)
    for r in results:
        r.setdefault("source", "local_roberta_transformer")
        r["degraded_mode"] = True
    return results


def classify(text: str, context: str = None, video_id: str = None) -> dict:
    return classify_batch([{"text": text, "context": context, "video_id": video_id}])[0]


def check_lexicon(text: str) -> dict:
    """Pass-through so callers that only need the fast rule-based layer
    (not a full model call) can still reach it via the router."""
    return _gemini.check_lexicon(text)


def build_fallback_justification(*args, **kwargs):
    return _gemini.build_fallback_justification(*args, **kwargs)


def has_negative_sentiment(text_or_sentiment: str) -> bool:
    """Pass-through for the fast heuristic negative-sentiment check in classify.py."""
    return _gemini.has_negative_sentiment(text_or_sentiment)


def is_degraded() -> bool:
    with _lock:
        return not _state["gemini_available"]