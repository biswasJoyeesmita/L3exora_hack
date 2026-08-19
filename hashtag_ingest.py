"""
hashtag_ingest.py
Simulates the government-entered-hashtag workflow:

  1. A government official enters a hashtag for a newly passed bill/rule
     (e.g. "#FarmerBill2026").
  2. The system finds every post/reel/video tagged with that hashtag.
  3. For each matching post, it pulls the CAPTION and every COMMENT on it.
  4. Every piece of text (captions + comments) goes through the existing
     classifier (classify_local.py) — no changes needed there, it already
     reads whole-sentence meaning.

NOTE on scope: real hashtag search against live Instagram requires the
Instagram Graph API (registered business account + Meta app review) -
not realistic to obtain before your deadline. This module searches a
MOCKED dataset (posts_mock.csv + comments_mock.csv) using the exact same
matching logic you'd use against the real API later - only the data
source changes, not the workflow.

NOTE on OCR: on-screen video text is NOT extracted here (explicitly out
of scope for now, per your instructions). Only caption text and comment
text are analyzed. Extending to on-screen text later would require an
OCR step before classification - a separate addition, not a change to
this ingestion logic.

Usage:
    python hashtag_ingest.py "#FarmerBill2026"
    python hashtag_ingest.py FarmerBill2026        (# is optional)
"""

import sys
import csv
from classify_local import classify

POSTS_PATH = "posts_mock.csv"
COMMENTS_PATH = "comments_mock.csv"
OUTPUT_PATH = "hashtag_report.txt"

TIER_LABELS = {
    1: "Neutral / lawful criticism",
    2: "Abusive / disrespectful",
    3: "Hate speech / incitement",
    4: "Direct threat",
}


def normalize_hashtag(tag: str) -> str:
    return tag.strip().lstrip("#").lower()


def load_posts():
    with open(POSTS_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_comments():
    with open(COMMENTS_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def find_posts_by_hashtag(hashtag: str, posts: list) -> list:
    """Case-insensitive match against each post's hashtags field."""
    target = normalize_hashtag(hashtag)
    matches = []
    for post in posts:
        post_tags = [normalize_hashtag(t) for t in post["hashtags"].split(",")]
        if target in post_tags:
            matches.append(post)
    return matches


def analyze_hashtag(hashtag: str):
    posts = load_posts()
    comments = load_comments()

    matched_posts = find_posts_by_hashtag(hashtag, posts)
    matched_post_ids = {p["post_id"] for p in matched_posts}
    matched_comments = [c for c in comments if c["post_id"] in matched_post_ids]

    return matched_posts, matched_comments


def build_report(hashtag: str, matched_posts: list, matched_comments: list) -> str:
    lines = []
    lines.append("=" * 100)
    lines.append(f"LEXORA — HASHTAG CONTENT SEARCH: #{normalize_hashtag(hashtag)}")
    lines.append("=" * 100)
    lines.append("")
    lines.append(
        "NOTE: Searching a simulated content set for this demo. In production this "
        "connects to the Instagram Graph API (pending Meta business/app review) using "
        "the same hashtag-match logic. On-screen video text is not analyzed yet (no "
        "OCR step) — only captions and comments."
    )
    lines.append("")
    lines.append(f"Posts/reels found tagged #{normalize_hashtag(hashtag)}: {len(matched_posts)}")
    lines.append(f"Total comments across those posts: {len(matched_comments)}")
    lines.append("")

    if not matched_posts:
        lines.append("No content found for this hashtag in the current dataset.")
        return "\n".join(lines)

    all_texts_classified = []
    flagged_count = 0

    for post in matched_posts:
        lines.append("-" * 100)
        lines.append(f"POST [{post['post_id']}] ({post['content_type']}) by @{post['username']}")
        lines.append(f"  Caption: \"{post['caption']}\"")

        caption_result = classify(post["caption"])
        all_texts_classified.append(("caption", post["post_id"], post["username"], post["caption"], caption_result))
        if caption_result["tier"] >= 2:
            flagged_count += 1
            lines.append(
                f"  >> CAPTION FLAGGED: Tier {caption_result['tier']} ({TIER_LABELS[caption_result['tier']]})"
            )
            if caption_result.get("flagged_terms"):
                lines.append(f"     Flagged terms: {', '.join(caption_result['flagged_terms'])}")
        else:
            lines.append(f"  Caption tier: {caption_result['tier']} (neutral/lawful, no action)")

        post_comments = [c for c in matched_comments if c["post_id"] == post["post_id"]]
        lines.append(f"  Comments on this post: {len(post_comments)}")
        for c in post_comments:
            result = classify(c["text"])
            all_texts_classified.append(("comment", c["comment_id"], c["username"], c["text"], result))
            if result["tier"] >= 2:
                flagged_count += 1
                lines.append(
                    f"    [FLAGGED] @{c['username']} — Tier {result['tier']} ({TIER_LABELS[result['tier']]})"
                )
                lines.append(f"      \"{c['text']}\"")
                if result.get("flagged_terms"):
                    lines.append(f"      Flagged terms: {', '.join(result['flagged_terms'])}")
        lines.append("")

    total_items = len(all_texts_classified)
    lines.append("=" * 100)
    lines.append("SUMMARY")
    lines.append("=" * 100)
    lines.append(f"Total items analyzed (captions + comments): {total_items}")
    lines.append(f"Flagged for human review: {flagged_count} ({flagged_count/total_items*100:.1f}%)")
    lines.append(
        f"Neutral/lawful, no action: {total_items - flagged_count} "
        f"({(total_items - flagged_count)/total_items*100:.1f}%)"
    )
    lines.append("")
    lines.append(
        "All flagged items above are queued for human review only. Nothing here "
        "is auto-reported or auto-actioned."
    )

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        hashtag = input("Enter hashtag to search (e.g. #FarmerBill2026): ").strip()
    else:
        hashtag = sys.argv[1]

    matched_posts, matched_comments = analyze_hashtag(hashtag)
    report = build_report(hashtag, matched_posts, matched_comments)

    print(report)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n\nFull report also written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()