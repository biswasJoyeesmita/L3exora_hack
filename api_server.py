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
        "degraded_mode": classify.is_degraded(),
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

    try:
        comments = fetch_youtube_comments(query, target_comments=target_comments)
    except RuntimeError as e:
        # e.g. missing YOUTUBE_API_KEY
        return jsonify({"error": str(e)}), 500

    results = []
    batch_size = 20
    for i in range(0, len(comments), batch_size):
        batch = comments[i:i + batch_size]
        results.extend(classify.classify_batch(batch))

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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)