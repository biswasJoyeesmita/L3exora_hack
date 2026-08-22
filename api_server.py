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
from flask import Flask, request, jsonify
from flask_cors import CORS

import classify

from youtube_ingest import fetch_youtube_comments, TIER_LABELS

app = Flask(__name__)
CORS(app)  # allow your frontend (different port/origin) to call this


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "degraded_mode": getattr(classify, "is_degraded", lambda: False)(),
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
    return jsonify(result)


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Body: {"query": "Farm Bill 2026", "target_comments": 100}
    Runs the full pipeline: fetches real YouTube comments for the topic,
    classifies them all, and returns tier stats + the flagged comments.
    This can take a while (network + classification) — for a live demo,
    keep target_comments modest (50-100) so it responds in reasonable time.
    """
    data = request.get_json(force=True, silent=True) or {}
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400
    target_comments = int(data.get("target_comments", 100))
    # Approximate target_comments using max_videos and max_comments_per_video
    max_comments_per_video = 10
    max_videos = max(1, target_comments // max_comments_per_video)

    try:
        comments = fetch_youtube_comments(
            query, 
            max_videos=max_videos, 
            max_comments_per_video=max_comments_per_video
        )
    except RuntimeError as e:
        # e.g. missing YOUTUBE_API_KEY
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
        if tier >= 2:
            flagged.append({
                "username": c["username"],
                "video_title": c["video_title"],
                "video_url": f"https://www.youtube.com/watch?v={c['video_id']}",
                "text": c["text"],
                "tier": tier,
                "tier_label": TIER_LABELS.get(tier, "Unknown"),
                "reason": res.get("flagged_reason"),
            })

    total = len(comments)
    degraded_count = sum(1 for r in results if r.get("degraded_mode"))

    return jsonify({
        "query": query,
        "total_comments": total,
        "tier_counts": tier_counts,
        "flagged_count": total - tier_counts.get(1, 0),
        "flagged": flagged,
        "degraded_comments": degraded_count,  # >0 means some results used the local fallback model
    })


@app.route("/api/generate_report", methods=["POST"])
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

    target_comments = min(200, max(1, int(data.get("target_comments", 200))))
    max_comments_per_video = 10
    max_videos = min(50, max(1, (target_comments + max_comments_per_video - 1) // max_comments_per_video))

    try:
        comments = fetch_youtube_comments(
            query,
            max_videos=max_videos,
            max_comments_per_video=max_comments_per_video,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    comments = comments[:target_comments]

    results = []
    classification_errors = 0
    batch_size = len(comments) or 1
    for start in range(0, len(comments), batch_size):
        batch = comments[start:start + batch_size]
        try:
            results.extend(classify.classify_batch([
                {"text": c["text"], "context": c.get("video_title")} for c in batch
            ]))
        except Exception as error:
            classification_errors += len(batch)
            print(f"[WARN] batch classification failed ({error}); using fallback results")
            for comment in batch:
                lex = classify.check_lexicon(comment["text"])
                raw_tier = lex.get("lexicon_tier", 1)
                tier = int(raw_tier) if raw_tier in (1, 2, 3, 4, 5) else 1
                if not lex.get("government_target_referenced"):
                    tier = 1
                results.append({
                    "tier": tier,
                    "government_target_referenced": bool(lex.get("government_target_referenced")),
                    "target_description": ", ".join(lex.get("target_terms_found", [])) or None,
                    "overall_sentiment": "rule-based fallback",
                    "flagged_terms": lex.get("matched_terms", []) if tier >= 2 else [],
                    "justification": "Gemini response was unavailable; rule-based screening result." if tier >= 2 else None,
                    "source": "lexicon_fallback",
                })

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
            comment_obj = {
                "tier": tier,
                "tierLabel": TIER_LABELS.get(tier, "Unknown"),
                "user": c.get("username", "Unknown"),
                "comment": c.get("text", ""),
                "reason": res.get("justification") or (
                    ", ".join(res.get("flagged_terms", [])) if res.get("flagged_terms") else
                    "Model flagged this content for human review."
                ),
                "videoTitle": video_title,
                "videoUrl": video_url,
            }
            vid_comments.append(comment_obj)
            flagged_comments.append(comment_obj)

        videos.append({
            "index": len(videos) + 1,
            "title": video_title,
            "url": video_url,
            "flaggedComments": len(flagged_items),
            "comments": vid_comments,
        })

    # Keep the live report within the target response time by deriving the
    # summary from the completed classifications instead of making another
    # Gemini request after the batch classification.
    flag_pct = (flagged_total / total * 100) if total > 0 else 0
    risk_level = "Low" if flag_pct < 5 else ("Moderate" if flag_pct < 15 else "High")
    social_impact = (
        f"Based on {total} YouTube comments scanned for '{query}', "
        f"{flagged_total} ({flag_pct:.1f}%) were flagged as abusive, disrespectful, or threatening "
        f"toward government entities. The remaining {total - flagged_total} ({100 - flag_pct:.1f}%) "
        f"were classified as lawful criticism or neutral discussion. RISK LEVEL: {risk_level}."
    )
    from youtube_ingest import build_report
    report_text = build_report(query, comments, results, social_impact=social_impact)

    # Cache structured JSON to model-output so Node.js can serve it as fallback
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        model_output_dir = os.path.join(script_dir, "..", "model-output")
        os.makedirs(model_output_dir, exist_ok=True)
        json_cache_path = os.path.join(model_output_dir, "youtube_feed_report.txt.json")
        import json as _json
        with open(json_cache_path, "w", encoding="utf-8") as _f:
            _f.write(_json.dumps({
                "source": "YouTube Data API",
                "reportType": "social-media-monitoring",
                "query": query,
                "commentsScanned": total,
                "flagged": flagged_total,
                "lawful": tier_counts.get(1, 0),
                "tierStats": {
                    "tier1": tier_counts.get(1, 0),
                    "tier2": tier_counts.get(2, 0),
                    "tier3": tier_counts.get(3, 0),
                    "tier4": tier_counts.get(4, 0),
                },
                "riskLevel": risk_level,
                "humanReviewOnly": True,
                "videos": videos,
                "socialImpactAssessment": social_impact,
                "reportText": report_text,
                "flaggedComments": flagged_comments,
                "totalVideos": len(videos),
            }))
    except Exception as _e:
        print(f"[WARN] Could not write JSON cache: {_e}")

    return jsonify({
        "source": "YouTube Data API",
        "reportType": "social-media-monitoring",
        "query": query,
        "commentsScanned": total,
        "flagged": flagged_total,
        "lawful": tier_counts.get(1, 0),
        "tierStats": {
            "tier1": tier_counts.get(1, 0),
            "tier2": tier_counts.get(2, 0),
            "tier3": tier_counts.get(3, 0),
            "tier4": tier_counts.get(4, 0),
        },
        "riskLevel": risk_level,
        "humanReviewOnly": True,
        "videos": videos,
        "socialImpactAssessment": social_impact,
        "reportText": report_text,
        "flaggedComments": flagged_comments,
        "totalVideos": len(videos),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
