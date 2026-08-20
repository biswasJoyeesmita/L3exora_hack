import os
import sys
from googleapiclient.discovery import build
from dotenv import load_dotenv


# SECURITY: API keys are loaded from a .env file, never hardcoded in source.
# Your .env file needs TWO keys now:
#   YOUTUBE_API_KEY=your_youtube_key_here
#   OPENROUTER_API_KEY=your_openrouter_key_here   (get one free at openrouter.ai)
# .env must be in .gitignore so it never gets committed to GitHub.
load_dotenv()
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
import classify_local as classify
TIER_LABELS = {
    1: "Lawful / Neutral",
    2: "Abusive / Disrespectful",
    3: "Hate Speech / Incitement",
    4: "Direct Threat",
}


def fetch_youtube_comments(query, max_videos=3, max_comments_per_video=10):
    """
    Searches YouTube for top videos matching `query` (e.g. #FarmerBill2026),
    extracts real user comments, and returns them in Lexora ingestion format.
    """
    if not YOUTUBE_API_KEY:
        raise RuntimeError(
            "YOUTUBE_API_KEY environment variable is not set. "
            "Set it before running this script - see the comment at the top of this file."
        )

    youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    # 1. Search for top videos matching the policy hashtag/keyword
    search_response = youtube.search().list(
        q=query,
        type="video",
        part="id,snippet",
        maxResults=max_videos,
        order="relevance"
    ).execute()

    extracted_comments = []

    for video_item in search_response.get("items", []):
        video_id = video_item["id"]["videoId"]
        video_title = video_item["snippet"]["title"]

        try:
            # 2. Fetch public comments for each video
            comment_response = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=max_comments_per_video,
                textFormat="plainText"
            ).execute()

            for item in comment_response.get("items", []):
                comment_data = item["snippet"]["topLevelComment"]["snippet"]
                extracted_comments.append({
                    "video_id": video_id,
                    "video_title": video_title,
                    "username": comment_data["authorDisplayName"],
                    "text": comment_data["textDisplay"]
                })
        except Exception:
            # Handles videos with comments disabled gracefully
            continue

    return extracted_comments


def generate_social_impact_summary(query, comments, results):
    """
    Uses Gemini to generate a plain-language social impact assessment:
    how is this policy/bill affecting society according to YouTube comments?
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
        prompt = f"""You are a social media analyst for a government policy monitoring system called Lexora.

A scan of YouTube comments for the topic "{query}" has been completed.

Stats:
- Total comments scanned: {total}
- Flagged (abusive/hateful/threatening toward government): {flagged} ({flag_pct:.1f}%)
- Lawful/neutral: {total - flagged} ({100 - flag_pct:.1f}%)

Sample flagged comments (abusive / disrespectful / threatening):
{chr(10).join(f'- "{t}"' for t in sample_flagged) or "(none)"}

Sample lawful comments (neutral / critical but legal):
{chr(10).join(f'- "{t}"' for t in sample_lawful) or "(none)"}

Write a concise 3-5 sentence SOCIAL IMPACT ASSESSMENT answering:
1. How is this topic/policy affecting public sentiment on social media?
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
            f"toward government entities. The remaining {total - flagged} ({100 - flag_pct:.1f}%) "
            f"were classified as lawful criticism or neutral discussion. "
            f"RISK LEVEL: {risk}."
        )


def build_report(query, comments, results):
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
    print("\n  [Generating social impact summary via Gemini...]")
    summary = generate_social_impact_summary(query, comments, results)
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
    output_path = "youtube_feed_report.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nFull structured report written to {output_path}")


if __name__ == "__main__":
    # Usage: python youtube_ingest.py "<search query>" [max_videos] [max_comments_per_video]
    search_tag = sys.argv[1] if len(sys.argv) > 1 else "Farm Bill 2026 India"
    videos = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    comments_per_video = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    run_live_pipeline(search_tag, max_videos=videos, max_comments_per_video=comments_per_video)

    