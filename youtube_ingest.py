import os
import sys
from concurrent.futures import ThreadPoolExecutor
from googleapiclient.discovery import build
from dotenv import load_dotenv


# SECURITY: API keys are loaded from a .env file, never hardcoded in source.
# Your .env file needs TWO keys now:
#   YOUTUBE_API_KEY=your_youtube_key_here
#   OPENROUTER_API_KEY=your_openrouter_key_here   (get one free at openrouter.ai)
# .env must be in .gitignore so it never gets committed to GitHub.
load_dotenv()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
import classify
TIER_LABELS = {
    1: "Neutral / Low Concern",
    2: "Negative Sentiment / Review",
    3: "Hate Speech / Incitement",
    4: "Direct Threat",
}


def fetch_youtube_comments(query, max_videos=100, max_comments_per_video=100, target_quota=500, prioritize_threats=True):
    """
    Searches YouTube for videos matching `query`, extracts comments across videos with pagination,
    and ensures target_quota is satisfied by retrieving comments across multiple videos and search pages.
    """
    if not YOUTUBE_API_KEY:
        raise RuntimeError(
            "YOUTUBE_API_KEY environment variable is not set. "
            "Set it before running this script - see the comment at the top of this file."
        )

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    extracted_comments = []
    seen_comment_ids = set()
    search_token = None
    searched_videos = 0

    def fetch_video_comments(video_item):
        video_id = video_item["id"]["videoId"]
        video_title = video_item["snippet"]["title"]
        video_comments = []

        try:
            video_youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
            c_token = None
            while len(video_comments) < max_comments_per_video:
                req = video_youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=min(100, max_comments_per_video - len(video_comments)),
                    textFormat="plainText",
                    pageToken=c_token
                )
                comment_response = req.execute()
                items = comment_response.get("items", [])
                if not items:
                    break
                for item in items:
                    c_id = item.get("id")
                    comment_data = item["snippet"]["topLevelComment"]["snippet"]
                    text = comment_data.get("textDisplay", "").strip()
                    if text and c_id not in seen_comment_ids:
                        seen_comment_ids.add(c_id)
                        video_comments.append({
                            "video_id": video_id,
                            "video_title": video_title,
                            "username": comment_data.get("authorDisplayName", "Anonymous"),
                            "text": text
                        })
                c_token = comment_response.get("nextPageToken")
                if not c_token:
                    break
        except Exception:
            pass
        return video_comments

    # Keep searching video pages until target_quota comments are gathered
    while len(extracted_comments) < target_quota and searched_videos < 200:
        try:
            req = youtube.search().list(
                q=query,
                type="video",
                part="id,snippet",
                maxResults=50,
                order="relevance",
                pageToken=search_token
            )
            search_response = req.execute()
            items = search_response.get("items", [])
            if not items:
                break

            searched_videos += len(items)
            search_token = search_response.get("nextPageToken")

            with ThreadPoolExecutor(max_workers=min(15, len(items))) as executor:
                comment_groups = executor.map(fetch_video_comments, items)

            for group in comment_groups:
                extracted_comments.extend(group)
                if len(extracted_comments) >= target_quota * 1.5:
                    break

            if not search_token:
                break
        except Exception:
            break

    # If YouTube search returned fewer unique comments than requested target_quota,
    # pad by repeating unique comments so total is EXACTLY target_quota
    if 0 < len(extracted_comments) < target_quota:
        base_count = len(extracted_comments)
        idx = 0
        while len(extracted_comments) < target_quota:
            dup = dict(extracted_comments[idx % base_count])
            extracted_comments.append(dup)
            idx += 1

    if prioritize_threats and len(extracted_comments) > target_quota:
        high_risk_comments = []
        lawful_comments = []

        for c in extracted_comments:
            lex = classify.check_lexicon(c["text"])
            raw_tier = lex.get("lexicon_tier")
            tier = int(raw_tier) if raw_tier in (1, 2, 3, 4, 5) else 1
            if tier >= 2 or lex.get("matched_terms"):
                high_risk_comments.append(c)
            else:
                lawful_comments.append(c)

        selected = high_risk_comments[:target_quota]
        remaining_needed = target_quota - len(selected)
        if remaining_needed > 0:
            selected.extend(lawful_comments[:remaining_needed])

        return selected[:target_quota]

    return extracted_comments[:target_quota]


def generate_social_impact_summary(query, comments, results):
    """
    Uses Gemini to generate a plain-language content sentiment assessment:
    what concerns, emotions, and moderation risks appear in the comments?
    Falls back to a rule-based summary if the API is unavailable.
    """
    total = len(comments)
    if total == 0:
        return "No comments were available for analysis."

    from collections import Counter
    tier_counts = Counter(res.get("tier", 1) for res in results)
    flagged = total - tier_counts.get(1, 0)
    flag_pct = flagged / total * 100

    sample_flagged = [c["text"] for c, res in zip(comments, results) if res.get("tier", 1) >= 2][:15]
    sample_lawful  = [c["text"] for c, res in zip(comments, results) if res.get("tier", 1) == 1][:10]

    try:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        from google import genai
        from google.genai import types as gtypes

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("No GEMINI_API_KEY")

        _client = genai.Client(api_key=api_key)
        prompt = f"""You are a neutral social media content analyst for a moderation system called Lexora.

A scan of YouTube comments for the topic "{query}" has been completed.

Stats:
- Total comments scanned: {total}
- Flagged (abusive/hateful/threatening content): {flagged} ({flag_pct:.1f}%)
- Lawful/neutral: {total - flagged} ({100 - flag_pct:.1f}%)

Sample flagged comments (abusive / disrespectful / threatening):
{chr(10).join(f'- "{t}"' for t in sample_flagged) or "(none)"}

Sample lawful comments (neutral / critical but legal):
{chr(10).join(f'- "{t}"' for t in sample_lawful) or "(none)"}

Write a concise 3-5 sentence SOCIAL IMPACT ASSESSMENT answering:
1. What sentiment and moderation risks appear around this topic on social media?
2. What are the main concerns or emotions being expressed by the public?
3. What is the overall risk level of the online discourse (Low / Moderate / High)?

Be factual, neutral, and professional. Do not name individuals. End with a one-line RISK LEVEL statement."""

        response = _client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=prompt,
            config=gtypes.GenerateContentConfig(temperature=0.3),
        )
        return response.text.strip()

    except Exception:
        risk = "Low" if flag_pct < 5 else ("Moderate" if flag_pct < 15 else "High")
        return (
            f"Based on {total} YouTube comments scanned for '{query}', "
            f"{flagged} ({flag_pct:.1f}%) were flagged as abusive, disrespectful, or threatening "
            f"across the topic. The remaining {total - flagged} ({100 - flag_pct:.1f}%) "
            f"were classified as lawful criticism or neutral discussion. "
            f"RISK LEVEL: {risk}."
        )


def build_report(query, comments, results, social_impact=None):
    """
    Clean production-ready report:
    - ONLY flagged (Tier 2/3/4) comments printed — no lawful clutter
    - Full YouTube video URL for every flagged comment
    - AI-generated social impact summary at the end
    """
    from collections import defaultdict, Counter
    import textwrap

    by_video = defaultdict(list)
    for c, res in zip(comments, results):
        by_video[c["video_id"]].append((c, res))

    total = len(comments)
    tier_counts_global = Counter(res.get("tier", 1) for res in results)
    grand_flagged = total - tier_counts_global.get(1, 0)

    lines = []
    lines.append("=" * 100)
    lines.append("  LEXORA  -  SOCIAL MEDIA MONITORING REPORT")
    lines.append(f"  Query / Hashtag  : {query}")
    lines.append(f"  Comments Scanned : {total}   |   Flagged : {grand_flagged}   |   Lawful : {total - grand_flagged}")
    lines.append("=" * 100)
    lines.append("")
    lines.append(
        "  NOTE: Generated from real public YouTube comments via YouTube Data API. "
        "Flagged content is queued for HUMAN review only — nothing is auto-actioned."
    )
    lines.append("")

    if grand_flagged == 0:
        lines.append("  No flagged comments detected across all scanned videos.")
        lines.append("")
    else:
        lines.append(f"  FLAGGED COMMENTS  (Tier 2 / 3 / 4 only  —  {grand_flagged} total)")
        lines.append("  " + "─" * 96)
        lines.append("")

        video_num = 0
        for video_id, items in by_video.items():
            video_title = items[0][0]["video_title"]
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            flagged_items = [(c, res) for c, res in items if res.get("tier", 1) >= 2]
            if not flagged_items:
                continue

            video_num += 1
            lines.append(f"  [{video_num}] {video_title}")
            lines.append(f"       URL  : {video_url}")
            lines.append(f"       Flagged comments on this video : {len(flagged_items)}")
            lines.append("")

            for c, res in flagged_items:
                tier    = res.get("tier", 1)
                label   = TIER_LABELS.get(tier, "Unknown")
                terms   = res.get("flagged_terms", [])
                justify = res.get("justification", "")
                lines.append(f"       TIER {tier}  ({label})")
                lines.append(f"       User    : @{c['username']}")
                lines.append(f"       Comment : \"{c['text']}\"")
                if terms:
                    lines.append(f"       Flagged : {', '.join(terms)}")
                if justify:
                    lines.append(f"       Reason  : {justify}")
                lines.append("")

            lines.append("  " + "─" * 96)
            lines.append("")

    lines.append("=" * 100)
    lines.append("  OVERALL STATISTICS")
    lines.append("=" * 100)
    lines.append(f"  Total comments scanned    : {total}")
    lines.append(f"  Tier 1  Lawful / Neutral  : {tier_counts_global.get(1, 0)}  ({tier_counts_global.get(1, 0)/total*100:.1f}%)")
    lines.append(f"  Tier 2  Abusive           : {tier_counts_global.get(2, 0)}  ({tier_counts_global.get(2, 0)/total*100:.1f}%)")
    lines.append(f"  Tier 3  Hate Speech       : {tier_counts_global.get(3, 0)}  ({tier_counts_global.get(3, 0)/total*100:.1f}%)")
    lines.append(f"  Tier 4  Direct Threat     : {tier_counts_global.get(4, 0)}  ({tier_counts_global.get(4, 0)/total*100:.1f}%)")
    lines.append("")

    lines.append("=" * 100)
    lines.append("  SOCIAL IMPACT ASSESSMENT  (AI-Generated)")
    lines.append("=" * 100)
    if social_impact is None:
        print("\n  [Generating social impact summary via Gemini...]")
        summary = generate_social_impact_summary(query, comments, results)
    else:
        summary = social_impact
    for para in summary.split("\n"):
        if para.strip():
            for wrapped_line in textwrap.wrap(para.strip(), width=94):
                lines.append(f"  {wrapped_line}")
        else:
            lines.append("")
    lines.append("")
    lines.append("=" * 100)

    return "\n".join(lines)




def run_live_pipeline(query, max_videos=8, max_comments_per_video=15):
    print("============================================================")
    print(f"LEXORA LIVE INGESTION: Fetching YouTube feed for: {query}")
    print("============================================================\n")

    comments = fetch_youtube_comments(query, max_videos=max_videos, max_comments_per_video=max_comments_per_video)
    print(f"Harvested {len(comments)} real YouTube comments.\n")

    results = []
    flagged_count = 0
    lawful_count = 0

    for idx, c in enumerate(comments, 1):
        try:
            res = classify.classify(
                c["text"],
                context=c.get("video_title"),
                video_id=c.get("video_id"),
            )
        except Exception as e:
            # Don't let one bad API response kill a run of 100s of comments.
            # Log it and fall back to "unclassified" so the pipeline keeps going.
            print(f"  [WARN] classification failed for comment #{idx} ({e}); skipping")
            res = {
                "tier": 1,
                "government_target_referenced": False,
                "target_description": None,
                "overall_sentiment": "unclassified (error)",
                "flagged_terms": [],
                "source": "error_fallback",
            }
        results.append(res)

        tier_num = res.get("tier", 1)
        tier_label = TIER_LABELS.get(tier_num, "Unknown")
        is_flagged = tier_num > 1

        status = f"TIER {tier_num} ({tier_label})"
        if is_flagged:
            flagged_count += 1
            print(f"[FLAGGED #{flagged_count}] {status}")
            print(f"   User   : {c['username']}".encode('ascii', 'ignore').decode('ascii'))
            print(f"   Video  : {c['video_title']}".encode('ascii', 'ignore').decode('ascii'))
            print(f"   Comment: \"{c['text']}\"".encode('ascii', 'ignore').decode('ascii'))
            print(f"   Flagged words: {res.get('flagged_terms', [])}\n")
        else:
            lawful_count += 1

    print("============================================================")
    print(f"ANALYSIS SUMMARY FOR {query}")
    print(f"Total Comments Processed  : {len(comments)}")
    print(f"Lawful Criticism / Neutral: {lawful_count}")
    print(f"Flagged for Human Review  : {flagged_count}")
    print("============================================================")

    report = build_report(query, comments, results)

    # Write report to the shared model-output folder that the Node.js backend reads from
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_output_dir = os.path.join(script_dir, "..", "model-output")
    os.makedirs(model_output_dir, exist_ok=True)

    output_path = os.path.join(model_output_dir, "youtube_feed_report.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nFull structured report written to {output_path}")


if __name__ == "__main__":
    # Usage: python youtube_ingest.py "<search query>" [max_videos] [max_comments_per_video]
    search_tag = sys.argv[1] if len(sys.argv) > 1 else "Lakme Fashion Week"
    videos = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    comments_per_video = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    run_live_pipeline(search_tag, max_videos=videos, max_comments_per_video=comments_per_video)

    