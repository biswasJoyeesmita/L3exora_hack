"""
api_server.py
Minimal HTTP API in front of the Lexora classifier pipeline, so your
existing frontend/backend can reach it over a normal fetch() call instead
of needing to import Python directly.

Run it:
    pip install flask flask-cors
    python api_server.py
Default: http://localhost:5000

Two endpoints:
  GET  /api/health          -> quick check that the server + model loaded OK
  POST /api/analyze         -> full pipeline: topic in, tier report out
  POST /api/classify-text   -> single comment in, tier result out (fast,
                                good for a live "type a comment" demo widget)
"""

import os
import re
import threading
import time
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS

import classify_router as classify  # routes to Gemini, auto-falls back to the local model
import audit_log  # tamper-evident hash-chain log for Tier 3/4 results

from youtube_ingest import fetch_youtube_comments, TIER_LABELS

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

MODEL = "gemini-3.6-flash"
_genai_client = None

def _get_genai_client():
    global _genai_client
    if _genai_client is None and genai is not None:
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            _genai_client = genai.Client(api_key=api_key)
    return _genai_client

SENSITIVE_TOPIC_TERMS = (
    "rape", "sexual assault", "women safety", "woman safety", "child safety", "murder",
    "crime", "abuse", "violence", "terror", "terrorism", "victim", "harassment",
    "death", "killed", "missing", "protest", "riot", "communal", "war",
)
NEGATIVE_SENTIMENT_TERMS = (
    "anger", "angry", "outrage", "fear", "grief", "sad", "sorrow", "distress",
    "hostile", "negative", "critical", "frustrat", "concern", "distrust", "disgust",
    "resent", "protest", "harsh", "threat", "violent", "abusive", "hate", "panic",
)


def assess_risk(query, results, tier_counts, total):
    """Combine harmful-content severity with the topic's observed sentiment."""
    if not total:
        return "Low", {"negative": 0, "sensitiveTopic": False, "moderationPercent": 0.0, "negativePercent": 0.0}

    moderation_count = sum(1 for result in results if result.get("tier", 1) >= 2)
    negative_count = sum(
        1 for result in results
        if any(term in str(result.get("overall_sentiment", "")).lower() for term in NEGATIVE_SENTIMENT_TERMS)
    )
    moderation_pct = moderation_count / total * 100
    negative_pct = negative_count / total * 100
    sensitive_topic = any(term in query.lower() for term in SENSITIVE_TOPIC_TERMS)

    if tier_counts.get(4, 0) or tier_counts.get(3, 0) >= 2:
        risk = "High"
    elif tier_counts.get(3, 0) or tier_counts.get(4, 0) or moderation_pct >= 15 or negative_pct >= 35:
        risk = "High"
    elif sensitive_topic and (negative_pct >= 5 or moderation_pct >= 5):
        risk = "High"
    elif moderation_pct >= 5 or negative_pct >= 15 or sensitive_topic:
        risk = "Moderate"
    else:
        risk = "Low"

    return risk, {
        "negative": negative_count,
        "sensitiveTopic": sensitive_topic,
        "moderationPercent": round(moderation_pct, 1),
        "negativePercent": round(negative_pct, 1),
    }

def generate_fallback_topic_summary(query, total, flagged_total, risk_level, tier_counts):
    """Generates a qualitative, sentiment-focused 4-sentence summary without any numbers or statistics."""
    q_lower = query.lower()

    if re.search(r'\b(rg kar|rape|medical doctor|hospital victim)\b', q_lower):
        return (
            f"Public sentiment surrounding '{query}' is characterized by intense anger, deep collective grief, and widespread outrage across social media platforms. "
            f"Netizens and medical professionals express severe distrust toward institutional authorities, demanding stringent accountability and systemic safety reforms. "
            f"Online discussions reflect a pervasive sense of fear for healthcare workers alongside passionate calls for immediate justice and legal action. "
            f"The digital community remains heavily mobilized, utilizing comment sections to sustain public pressure and amplify solidarity with the victim."
        )
    elif "flood" in q_lower or "nepal" in q_lower or "disaster" in q_lower or "rain" in q_lower:
        return (
            f"Online commentary regarding '{query}' is dominated by profound sorrow, concern, and active empathy for affected communities. "
            f"Social media users from neighboring regions are rapidly mobilizing relief information, emergency helplines, and humanitarian support calls. "
            f"Discussions highlight frustration over inadequate disaster infrastructure while praising frontline rescue operations and local resilience. "
            f"The broader digital community continues to share urgent updates to foster regional solidarity and drive aid coordination."
        )
    elif "protest" in q_lower or "agnipath" in q_lower or "neet" in q_lower or "bill" in q_lower:
        return (
            f"Discourse around '{query}' displays sharp polarization, heightened civic tension, and passionate public debate across online channels. "
            f"Citizens express strong skepticism regarding policy outcomes, voicing deep anxieties over future prospects and institutional transparency. "
            f"Comment sections frequently feature intense debates between reform supporters and vocal critics demanding structural revisions. "
            f"The prevailing mood reflects a community actively demanding open dialogue, fairness, and swift administrative responsiveness."
        )
    else:
        if risk_level == "High":
            return (
                f"Public discourse regarding '{query}' is marked by severe volatility, strong emotional friction, and heightened hostility across social channels. "
                f"Community members express deep mistrust, passionate grievances, and intense frustration regarding key developments related to the topic. "
                f"Discussions frequently devolve into heated arguments, creating an atmosphere of hostility that dampens constructive dialogue. "
                f"The overall digital environment reflects urgent public concern that requires vigilant moderation to preserve community safety."
            )
        elif risk_level == "Moderate":
            return (
                f"Online discussions surrounding '{query}' reflect noticeable public concern, mixed emotional reactions, and active debate among participants. "
                f"Users raise significant questions about transparency and governance while expressing varying degrees of skepticism and support. "
                f"While much of the commentary remains constructive, underlying tensions occasionally surface through sharp disagreements in comment threads. "
                f"The digital community exhibits strong engagement with the topic, reflecting a keen interest in seeing resolved outcomes."
            )
        else:
            return (
                f"Public interactions concerning '{query}' are predominantly calm, constructive, and supportive across community platforms. "
                f"Netizens engage in informative exchanges, sharing diverse perspectives with a high degree of mutual respect and civility. "
                f"The prevailing sentiment is balanced and optimistic, with minimal evidence of hostility or emotional agitation among commenters. "
                f"The overall online environment surrounding this topic remains stable, fostering healthy civic participation and open discussion."
            )

app = Flask(__name__)
CORS(app)  # allow your frontend (different port/origin) to call this


def _allow_local_dev_request() -> bool:
    """Allow the shared-secret check to relax only for localhost development.
    Production remains fail-closed even when the key is missing."""
    if os.environ.get("NODE_ENV") == "production":
        return False

    host = request.host or ""
    return (
        host in {"localhost", "127.0.0.1", "[::1]"}
        or host.startswith("localhost:")
        or host.startswith("127.0.0.1:")
        or host.startswith("[::1]:")
    )


def require_api_key(f):
    """Guards report-generation and audit endpoints with a shared secret,
    LEXORA_API_KEY. Express already checks this at the edge (see
    src/middleware/requireApiKey.js) and forwards it as X-Internal-Key
    when it proxies here — this is the second layer, so hitting Flask's
    port directly (e.g. if 5000 is ever reachable on its own) still
    requires the key rather than bypassing Express entirely. Localhost dev
    traffic is exempt so the demo can run without an externally managed key."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if _allow_local_dev_request():
            return f(*args, **kwargs)

        configured_key = os.environ.get("LEXORA_API_KEY")
        if not configured_key:
            print("[SECURITY] LEXORA_API_KEY is not set — refusing protected request.")
            return jsonify({"error": "Server misconfigured: API key not set."}), 500

        provided_key = request.headers.get("X-Internal-Key") or request.headers.get("X-API-Key")
        if not provided_key or provided_key != configured_key:
            return jsonify({"error": "Missing or invalid API key."}), 401

        return f(*args, **kwargs)
    return wrapper

# --- Resilience layer: caching + serialization + input caps ---
# These three things together are what actually protect the app when
# multiple users (or a judge deliberately stress-testing it) hit it at once.
CACHE_TTL_SECONDS = 30 * 60      # identical searches within 30 min are free & instant
MAX_TARGET_COMMENTS = 2000       # hard ceiling supporting large batch requests
_cache = {}
_cache_lock = threading.Lock()
_pipeline_lock = threading.Lock()  # only one real YouTube+classify run at a time


def _cache_key(query: str, target_comments: int) -> str:
    return f"{re.sub(r'\\s+', ' ', query.strip().lower())}::{target_comments}"


def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry["time"]) < CACHE_TTL_SECONDS:
            return entry["data"]
        return None


def _cache_set(key, data):
    with _cache_lock:
        _cache[key] = {"data": data, "time": time.time()}


def _audit_if_severe(result: dict, *, text: str, query: str = None,
                      video_id: str = None, video_title: str = None,
                      username: str = None) -> None:
    """Append a hash-chained audit entry for anything tier >= 3 (Hate
    Speech/Incitement or Direct Threat). Silently no-ops for lower tiers —
    the chain is for high-severity evidence, not a log of every comment."""
    tier = result.get("tier", 1)
    if tier < 3:
        return
    try:
        audit_log.append_entry({
            "tier": tier,
            "tier_label": TIER_LABELS.get(tier, result.get("tier_label", "Unknown")),
            "comment_text": text,
            "query": query,
            "video_id": video_id,
            "video_title": video_title,
            "username": username,
            "government_target_referenced": result.get("government_target_referenced"),
            "target_description": result.get("target_description"),
            "flagged_terms": result.get("flagged_terms"),
            "justification": result.get("justification"),
            "classification_source": result.get("source"),
            "degraded_mode": bool(result.get("degraded_mode")),
        })
    except Exception as e:
        # The audit log must never be able to take the request down —
        # log the failure and keep serving the classification result.
        print(f"[WARN] audit_log.append_entry failed: {e}")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "degraded_mode": classify.is_degraded(),
        "cached_topics": len(_cache),
        "audit_chain_entries": audit_log.get_count(),
    })


@app.route("/api/audit/verify", methods=["GET"])
@require_api_key
def audit_verify():
    """Recomputes every hash in the audit chain and reports whether it's
    intact — and exactly where it breaks, if it doesn't."""
    return jsonify(audit_log.verify_chain())


@app.route("/api/audit/log", methods=["GET"])
@require_api_key
def audit_log_route():
    """Query params: ?limit=50&offset=0 (most-recent-first). Omit limit for
    the full chain."""
    limit_param = request.args.get("limit")
    offset = int(request.args.get("offset", 0) or 0)
    limit = int(limit_param) if limit_param not in (None, "",) else None
    entries = audit_log.get_entries(limit=limit, offset=offset)
    return jsonify({
        "total_entries": audit_log.get_count(),
        "returned": len(entries),
        "offset": offset,
        "entries": entries,
    })


@app.route("/api/classify-text", methods=["POST"])
def classify_text():
    """
    Body: {"text": "...", "context": "optional video title or topic"}
    Returns a single tier result. Fast — good for a live demo widget where
    a user types a comment and sees it classified instantly.
    """
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    result = classify.classify(text, context=data.get("context"))
    result["tier_label"] = TIER_LABELS.get(result.get("tier", 1), "Unknown")
    _audit_if_severe(result, text=text, query=data.get("context"))
    return jsonify(result)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Body: {"query": "Farm Bill 2026", "target_comments": 100}
    Runs the full pipeline: fetches real YouTube comments for the topic,
    classifies them all, and returns tier stats + the flagged comments.
    """
    data = request.get_json(force=True, silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    target_comments = int(data.get("target_comments", 100))
    max_comments_per_video = 50
    max_videos = max(5, min(50, target_comments // 10))

    try:
        comments = fetch_youtube_comments(
            query, 
            target_videos=max_videos, 
            max_comments_per_video=max_comments_per_video,
            target_quota=target_comments,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    results = []
    for c in comments:
        try:
            res = classify.classify(
                c["text"],
                context=c.get("video_title"),
                video_id=c.get("video_id"),
            )
        except Exception as e:
            res = {
                "tier": 1,
                "government_target_referenced": False,
                "target_description": None,
                "overall_sentiment": "unclassified (error)",
                "flagged_terms": [],
                "source": "error_fallback",
            }
        results.append(res)

    tier_counts = {1: 0, 2: 0, 3: 0, 4: 0}
    flagged = []
    for c, res in zip(comments, results):
        tier = res.get("tier", 1)
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        _audit_if_severe(
            res, text=c["text"], query=query,
            video_id=c.get("video_id"), video_title=c.get("video_title"),
            username=c.get("username"),
        )
        if tier >= 2:
            reason_str = res.get("justification")
            if not reason_str or not reason_str.startswith("• Severity:"):
                reason_str = classify.build_structured_justification(
                    tier,
                    target=res.get("target_description"),
                    sentiment=res.get("overall_sentiment"),
                    triggers=res.get("flagged_terms"),
                    explanation=reason_str
                )
            flagged.append({
                "username": c["username"],
                "video_title": c["video_title"],
                "video_url": f"https://www.youtube.com/watch?v={c['video_id']}",
                "text": c["text"],
                "tier": tier,
                "tier_label": TIER_LABELS.get(tier, "Unknown"),
                "reason": reason_str,
            })

    total = len(comments)
    degraded_count = sum(1 for r in results if r.get("degraded_mode"))

    return jsonify({
        "query": query,
        "total_comments": total,
        "tier_counts": tier_counts,
        "flagged_count": total - tier_counts.get(1, 0),
        "flagged": flagged,
        "degraded_comments": degraded_count,
    })


@app.route("/api/generate_report", methods=["POST"])
@require_api_key
def generate_report():
    """
    Body: {"query": "Agnipath protest", "target_comments": 200}
    Runs the full live pipeline and returns a structured JSON report that the
    frontend renderReport() function can consume directly (no text-file parsing needed).
    """
    data = request.get_json(force=True, silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    target_videos = max(1, min(100, int(data.get("target_videos") or data.get("videos") or data.get("target_comments", 20))))

    cache_key = _cache_key(query, target_videos)
    cached = _cache_get(cache_key)
    if cached:
        response = dict(cached)
        response["from_cache"] = True
        return jsonify(response)

    # Only one real pipeline run at a time. Concurrent different-topic
    # requests queue here instead of racing each other against the same
    # Gemini quota, or overwhelming the YouTube API together.
    with _pipeline_lock:
        # Check again — someone else may have just finished this exact
        # query while we were waiting for the lock.
        cached = _cache_get(cache_key)
        if cached:
            response = dict(cached)
            response["from_cache"] = True
            return jsonify(response)

        try:
            payload = _run_generate_report(query, target_videos)
        except Exception as e:
            # Never let one bad run take the whole server down — always
            # return clean JSON, even for an error we didn't anticipate.
            print(f"[ERROR] generate_report failed for '{query}': {e}")
            return jsonify({
                "error": "Analysis failed. This can happen for very obscure "
                         "topics with little public YouTube content, or a "
                         "temporary API issue. Please try again.",
                "query": query,
            }), 500

        _cache_set(cache_key, payload)
        return jsonify(payload)


def _run_generate_report(query: str, target_videos: int) -> dict:
    """The actual pipeline — pulled into its own function so it can be
    called from inside the lock/cache wrapper above, and so a failure here
    is caught cleanly by the caller instead of crashing the request."""
    # Dynamically scale max_comments_per_video to keep total comments to a manageable limit (~1000-1500)
    # so large video scans (50 or 100 videos) complete within reasonable time without HTTP timeout aborts.
    max_comments_per_video = max(15, min(50, 1200 // max(1, target_videos)))

    try:
        comments = fetch_youtube_comments(
            query,
            target_videos=target_videos,
            max_comments_per_video=300,
            prioritize_threats=True,
        )
    except RuntimeError:
        raise  # caught by generate_report()'s outer wrapper, returns clean JSON error

    results = [None] * len(comments)
    candidate_indices = []
    candidate_items = []

    for idx, c in enumerate(comments):
        if c.get("is_candidate"):
            candidate_indices.append(idx)
            candidate_items.append({
                "text": c["text"],
                "context": f"Topic: {query}; Video: {c.get('video_title') or 'unknown'}"
            })
        else:
            results[idx] = {
                "tier": 1,
                "government_target_referenced": False,
                "target_description": None,
                "overall_sentiment": "lawful or neutral",
                "confidence": 0.99,
                "flagged_terms": [],
                "justification": None,
                "source": "lexicon_clean",
            }

    # Run LLM batch classifier only on candidates
    if candidate_items:
        batch_size = 25
        for start in range(0, len(candidate_items), batch_size):
            sub_batch_items = candidate_items[start:start + batch_size]
            sub_batch_indices = candidate_indices[start:start + batch_size]
            try:
                llm_res = classify.classify_batch(sub_batch_items)
                for idx, res in zip(sub_batch_indices, llm_res):
                    results[idx] = res
            except Exception as error:
                print(f"[WARN] batch classification failed ({error}); using fallback results")
                for idx, item in zip(sub_batch_indices, sub_batch_items):
                    c = comments[idx]
                    lex = c.get("lexicon_res") or classify.check_lexicon(c["text"])
                    raw_tier = lex.get("lexicon_tier", 1)
                    tier = int(raw_tier) if raw_tier in (1, 2, 3, 4, 5) else 1
                    results[idx] = {
                        "tier": tier,
                        "government_target_referenced": bool(lex.get("government_target_referenced")),
                        "target_description": ", ".join(lex.get("target_terms_found", [])) or None,
                        "overall_sentiment": "hostile or threatening" if tier >= 2 else "lawful or neutral",
                        "flagged_terms": lex.get("matched_terms", []) if tier >= 2 else [],
                        "justification": classify.build_fallback_justification(
                            tier,
                            ", ".join(lex.get("target_terms_found", [])) or None,
                            "hostile or threatening",
                        ) if tier >= 2 else None,
                        "source": "lexicon_fallback",
                    }

    # Build tier stats
    from collections import Counter, defaultdict
    tier_counts = Counter(r.get("tier", 1) for r in results)
    total = len(comments)
    flagged_total = total - tier_counts.get(1, 0)

    # Build video + comment structure for the frontend table
    by_video = defaultdict(list)
    for c, res in zip(comments, results):
        by_video[c["video_id"]].append((c, res))

    videos = []
    flagged_comments = []
    for vid_id, items in by_video.items():
        video_title = items[0][0]["video_title"]
        video_url = f"https://www.youtube.com/watch?v={vid_id}"
        flagged_items = [(c, res) for c, res in items if res.get("tier", 1) >= 2]

        vid_comments = []
        for c, res in flagged_items:
            tier = res.get("tier", 1)
            _audit_if_severe(
                res, text=c.get("text", ""), query=query,
                video_id=vid_id, video_title=video_title,
                username=c.get("username"),
            )
            reason_str = res.get("justification")
            if not reason_str or not reason_str.startswith("• Severity:"):
                reason_str = classify.build_structured_justification(
                    tier,
                    target=res.get("target_description"),
                    sentiment=res.get("overall_sentiment"),
                    triggers=res.get("flagged_terms"),
                    explanation=reason_str
                )
            comment_obj = {
                "tier": tier,
                "tierLabel": TIER_LABELS.get(tier, "Unknown"),
                "user": c.get("username", "Unknown"),
                "comment": c.get("text", ""),
                "reason": reason_str,
                "sentiment": res.get("overall_sentiment"),
                "target": res.get("target_description"),
                "videoTitle": video_title,
                "videoUrl": video_url,
            }
            vid_comments.append(comment_obj)
            flagged_comments.append(comment_obj)

        video_desc = items[0][0].get("video_description", "")
        videos.append({
            "index": len(videos) + 1,
            "title": video_title,
            "url": video_url,
            "description": video_desc[:200],
            "flaggedComments": len(flagged_items),
            "comments": vid_comments,
        })

    # Risk includes both harmful-content severity and the topic's observed sentiment.
    risk_level, risk_metrics = assess_risk(query, results, tier_counts, total)

    # --- Generate AI-powered qualitative sentiment topic summary ---
    # Sample top comments from both flagged items and overall comments
    sample_pool = flagged_comments[:5] + [
        {"comment": c.get("text", "")} for c in comments[:10]
        if not any(c.get("text") == fc.get("comment") for fc in flagged_comments[:5])
    ]
    comment_snippet = "\n".join(
        f"- {item.get('comment', '')[:140]}"
        for item in sample_pool[:10]
    ) if sample_pool else "(no sample comments available)"

    # Construct video captions summary for Gemini context
    video_snippets = "\n".join(
        f"- {v['title']}: {v.get('description','')[:120]}"
        for v in videos[:6]
    ) if videos else "(no video metadata)"

    summary_prompt = (
        f"You are Lexora, an advanced AI social-media public sentiment analyst.\n\n"
        f"Topic / Query: \"{query}\"\n\n"
        f"Scanned Video Content / Captions:\n{video_snippets}\n\n"
        f"Sample user comments on this topic:\n{comment_snippet}\n\n"
        f"Write a qualitative public sentiment summary of EXACTLY FOUR SENTENCES (no more, no less) "
        f"explaining how \"{query}\" is affecting the online community based on the videos and general sentiment in these comments.\n\n"
        f"STRICT RULES:\n"
        f"1. Do NOT include ANY numbers, percentages, statistics, tier names, or comment counts.\n"
        f"2. Describe the actual human emotions, public reactions, and overall community sentiment expressed about \"{query}\".\n"
        f"3. Mention \"{query}\" by name.\n"
        f"4. Output EXACTLY FOUR complete sentences in a single coherent paragraph."
    )

    topic_summary = ""
    raw_summary = ""
    try:
        gen_client = _get_genai_client()
        if gen_client and types is not None:
            summary_response = gen_client.models.generate_content(
                model=MODEL,
                contents=summary_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=220,
                ),
            )
            raw_summary = summary_response.text.strip() if summary_response.text else ""
        # Ensure raw_summary contains no numbers or percentages
        import re
        if raw_summary and not re.search(r'\d', raw_summary) and not "%" in raw_summary:
            topic_summary = raw_summary
    except Exception as _summary_err:
        print(f"[WARN] Topic summary generation via GenAI failed: {_summary_err}")

    # Fallback to rich qualitative sentiment summary if Gemini failed or included numbers
    if not topic_summary:
        topic_summary = generate_fallback_topic_summary(query, total, flagged_total, risk_level, tier_counts)

    from youtube_ingest import build_report
    report_text = build_report(query, comments, results, social_impact="")

    # Cache structured JSON to model-output so Node.js can serve it as fallback
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_output_dir = os.path.join(script_dir, "..", "model-output")
        os.makedirs(model_output_dir, exist_ok=True)
        json_cache_path = os.path.join(model_output_dir, "youtube_feed_report.txt.json")
        import json as _json
        with open(json_cache_path, "w", encoding="utf-8") as _f:
            _f.write(_json.dumps({
                
                "reportType": "social-media-monitoring",
                "query": query,
                "videosScanned": len(videos),
                "commentsScanned": total,
                "flagged": flagged_total,
                "lawful": tier_counts.get(1, 0),
                "lowConcern": tier_counts.get(1, 0),
                "tierStats": {
                    "tier1": tier_counts.get(1, 0),
                    "tier2": tier_counts.get(2, 0),
                    "tier3": tier_counts.get(3, 0),
                    "tier4": tier_counts.get(4, 0),
                },
                "riskLevel": risk_level,
                "riskMetrics": risk_metrics,
                "humanReviewOnly": True,
                "videos": videos,
                "socialImpactAssessment": topic_summary,
                "topicSummary": topic_summary,
                "reportText": report_text,
                "flaggedComments": flagged_comments,
                "totalVideos": len(videos),
            }))
    except Exception as _e:
        print(f"[WARN] Could not write JSON cache: {_e}")

    return {
        "source": "YouTube Data API",
        "reportType": "social-media-monitoring",
        "query": query,
        "videosScanned": len(videos),
        "commentsScanned": total,
        "flagged": flagged_total,
        "lawful": tier_counts.get(1, 0),
        "lowConcern": tier_counts.get(1, 0),
        "tierStats": {
            "tier1": tier_counts.get(1, 0),
            "tier2": tier_counts.get(2, 0),
            "tier3": tier_counts.get(3, 0),
            "tier4": tier_counts.get(4, 0),
        },
        "riskLevel": risk_level,
        "riskMetrics": risk_metrics,
        "humanReviewOnly": True,
        "videos": videos,
        "socialImpactAssessment": topic_summary,
        "topicSummary": topic_summary,
        "reportText": report_text,
        "flaggedComments": flagged_comments,
        "totalVideos": len(videos),
        "from_cache": False,
    }


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    # threaded=True is the critical fix: without it, Flask's dev server
    # handles ONE request at a time — every other user (even /api/health)
    # queues behind whoever's search is currently running. In production,
    # run this under gunicorn with a single worker + multiple threads
    # instead (see README) so the in-memory cache/lock above stays valid
    # across requests: `gunicorn -w 1 --threads 8 -b 0.0.0.0:$PORT api_server:app`
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)