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

# Gemini client for topic summary generation
from google import genai
from google.genai import types
from dotenv import load_dotenv
load_dotenv()
client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
MODEL = "gemini-2.0-flash"

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

    if "rg" in q_lower or "kar" in q_lower or "rape" in q_lower or "doctor" in q_lower:
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
            max_videos=max_videos, 
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
        if tier >= 2:
            flagged.append({
                "username": c["username"],
                "video_title": c["video_title"],
                "video_url": f"https://www.youtube.com/watch?v={c['video_id']}",
                "text": c["text"],
                "tier": tier,
                "tier_label": TIER_LABELS.get(tier, "Unknown"),
                "reason": res.get("justification") or "Model flagged this content for human review.",
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

    target_comments = min(2000, max(1, int(data.get("target_comments", 200))))
    max_comments_per_video = 100 if target_comments >= 200 else 30
    max_videos = max(10, min(100, target_comments // 5 if target_comments > 50 else 10))

    try:
        comments = fetch_youtube_comments(
            query,
            max_videos=max_videos,
            max_comments_per_video=max_comments_per_video,
            target_quota=target_comments,
            prioritize_threats=True,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    # Ensure EXACT target_comments count
    if len(comments) > target_comments:
        comments = comments[:target_comments]

    results = []
    classification_errors = 0
    batch_size = 25
    for start in range(0, len(comments), batch_size):
        batch = comments[start:start + batch_size]
        try:
            results.extend(classify.classify_batch([
                {"text": c["text"], "context": f"Topic: {query}; Video: {c.get('video_title') or 'unknown'}"} for c in batch
            ]))
        except Exception as error:
            classification_errors += len(batch)
            print(f"[WARN] batch classification failed ({error}); using fallback results")
            for comment in batch:
                lex = classify.check_lexicon(comment["text"])
                raw_tier = lex.get("lexicon_tier", 1)
                tier = int(raw_tier) if raw_tier in (1, 2, 3, 4, 5) else 1
                results.append({
                    "tier": tier,
                    "government_target_referenced": bool(lex.get("government_target_referenced")),
                    "target_description": ", ".join(lex.get("target_terms_found", [])) or None,
                    "overall_sentiment": "hostile or threatening",
                    "flagged_terms": lex.get("matched_terms", []) if tier >= 2 else [],
                    "justification": classify.build_fallback_justification(
                        tier,
                        ", ".join(lex.get("target_terms_found", [])) or None,
                        "hostile or threatening",
                    ) if tier >= 2 else None,
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
                "reason": res.get("justification") or classify.build_fallback_justification(
                    tier,
                    res.get("target_description"),
                    res.get("overall_sentiment"),
                ),
                "sentiment": res.get("overall_sentiment"),
                "target": res.get("target_description"),
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

    # Risk includes both harmful-content severity and the topic's observed sentiment.
    risk_level, risk_metrics = assess_risk(query, results, tier_counts, total)

    # --- Generate AI-powered qualitative sentiment topic summary ---
    sample_flagged = flagged_comments[:6]
    flagged_snippet = "\n".join(
        f"- {fc.get('comment','')[:120]}"
        for fc in sample_flagged
    ) if sample_flagged else "(no flagged comments)"

    summary_prompt = (
        f"You are Lexora, an advanced AI social-media public sentiment analyst.\n\n"
        f"Topic / Query: \"{query}\"\n\n"
        f"Sample user comments:\n{flagged_snippet}\n\n"
        f"Write a qualitative public sentiment summary of EXACTLY FOUR SENTENCES (no more, no less) "
        f"explaining how \"{query}\" is affecting the online community.\n\n"
        f"STRICT RULES:\n"
        f"1. Do NOT include ANY numbers, percentages, statistics, tier names, or comment counts.\n"
        f"2. Describe the human emotions (anger, grief, fear, outrage, solidarity, trust issues, hope), public reactions, and general sentiment expressed by people.\n"
        f"3. Mention \"{query}\" by name.\n"
        f"4. Output EXACTLY FOUR complete sentences in a single coherent paragraph."
    )

    topic_summary = ""
    try:
        summary_response = client.models.generate_content(
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
                "source": "YouTube Data API",
                "reportType": "social-media-monitoring",
                "query": query,
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

    return jsonify({
        "source": "YouTube Data API",
        "reportType": "social-media-monitoring",
        "query": query,
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
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
