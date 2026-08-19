"""
analyze_feed.py
Per-policy dashboard: for each policy in policies.json, finds every post
tagged with a matching hashtag/keyword, classifies its caption AND every
comment on it, and reports a neutral-vs-flagged breakdown per policy.

Now built on posts_mock.csv + comments_mock.csv (posts carry hashtags,
comments link to posts via post_id) — the same data model used by
hashtag_ingest.py, so there's one consistent mock dataset across the
whole project instead of two.

Usage:
    python analyze_feed.py
"""

import csv
from collections import defaultdict
from policy_context import load_policies
from classify_local import classify

POSTS_PATH = "posts_mock.csv"
COMMENTS_PATH = "comments_mock.csv"
OUTPUT_PATH = "feed_report.txt"

TIER_LABELS = {
    1: "Neutral / lawful criticism",
    2: "Abusive / disrespectful",
    3: "Hate speech / incitement",
    4: "Direct threat",
}


def normalize(tag):
    return tag.strip().lstrip("#").lower()


def load_posts():
    with open(POSTS_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_comments():
    with open(COMMENTS_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def match_post_to_policy(post, policies):
    """
    Returns the policy_id this post belongs to, based on whether any of
    the post's hashtags matches (or is contained in / contains) any of
    the policy's keywords. Returns None if no policy matches.
    """
    post_tags = [normalize(t) for t in post["hashtags"].split(",")]

    for policy_id, policy in policies.items():
        policy_keywords = [normalize(k) for k in policy["keywords"]]
        for tag in post_tags:
            for kw in policy_keywords:
                if tag == kw or tag in kw or kw in tag:
                    return policy_id
    return None


def main():
    policies = load_policies()
    posts = load_posts()
    comments = load_comments()

    comments_by_post = defaultdict(list)
    for c in comments:
        comments_by_post[c["post_id"]].append(c)

    # group posts (and their comments) by matched policy
    by_policy = defaultdict(list)
    unmatched_posts = []

    for post in posts:
        policy_id = match_post_to_policy(post, policies)
        if policy_id is None:
            unmatched_posts.append(post)
            continue

        caption_result = classify(post["caption"])
        by_policy[policy_id].append({
            "type": "caption",
            "post_id": post["post_id"],
            "username": post["username"],
            "text": post["caption"],
            **caption_result,
        })

        for c in comments_by_post.get(post["post_id"], []):
            comment_result = classify(c["text"])
            by_policy[policy_id].append({
                "type": "comment",
                "post_id": post["post_id"],
                "username": c["username"],
                "text": c["text"],
                **comment_result,
            })

    print(f"Loaded {len(posts)} posts and {len(comments)} comments.")
    if unmatched_posts:
        print(f"({len(unmatched_posts)} post(s) didn't match any policy keywords - check hashtags/keywords)")
    print()

    report_lines = []
    report_lines.append("=" * 100)
    report_lines.append("LEXORA - POLICY-TAGGED CONTENT MONITORING REPORT (mocked Instagram feed)")
    report_lines.append(f"Posts analyzed: {len(posts) - len(unmatched_posts)}   Comments analyzed: {len(comments)}")
    report_lines.append("=" * 100)
    report_lines.append("")
    report_lines.append(
        "NOTE: This is a simulated content feed for demo purposes. In production this "
        "would connect to a real social platform API. Flagged content is queued for "
        "HUMAN review only - nothing here is auto-reported or auto-actioned."
    )
    report_lines.append("")

    grand_total = 0
    grand_flagged = 0

    for policy_id, policy in policies.items():
        items = by_policy.get(policy_id, [])
        total = len(items)
        if total == 0:
            continue

        tier_counts = defaultdict(int)
        for item in items:
            tier_counts[item["tier"]] += 1

        neutral_count = tier_counts.get(1, 0)
        flagged_count = total - neutral_count
        flagged_pct = (flagged_count / total * 100) if total else 0

        grand_total += total
        grand_flagged += flagged_count

        report_lines.append("-" * 100)
        report_lines.append(f"POLICY: {policy['title']}  (id: {policy_id})")
        report_lines.append(f"  {policy['description']}")
        report_lines.append(f"  Keywords tracked: {', '.join(policy['keywords'])}")
        report_lines.append("-" * 100)
        report_lines.append(f"  Total items (captions + comments): {total}")
        report_lines.append(f"  Neutral/lawful (tier 1): {neutral_count}  ({neutral_count/total*100:.0f}%)")
        report_lines.append(f"  Flagged (tier 2-4)     : {flagged_count}  ({flagged_pct:.0f}%)")
        for t in (2, 3, 4):
            if tier_counts.get(t):
                report_lines.append(f"      Tier {t} ({TIER_LABELS[t]}): {tier_counts[t]}")
        report_lines.append("")

        flagged_items = [i for i in items if i["tier"] >= 2]
        if flagged_items:
            report_lines.append("  Flagged items (queued for human review):")
            for item in flagged_items:
                kind = "CAPTION" if item["type"] == "caption" else "comment"
                report_lines.append(
                    f"    [{item['post_id']}] {kind} @{item['username']} - Tier {item['tier']} ({TIER_LABELS[item['tier']]})"
                )
                report_lines.append(f"      \"{item['text']}\"")
                if item.get("flagged_terms"):
                    report_lines.append(f"      Flagged terms: {', '.join(item['flagged_terms'])}")
            report_lines.append("")

    report_lines.append("=" * 100)
    report_lines.append("OVERALL SUMMARY")
    report_lines.append("=" * 100)
    report_lines.append(f"Total items analyzed      : {grand_total}")
    if grand_total:
        report_lines.append(f"Flagged for human review  : {grand_flagged}  ({grand_flagged/grand_total*100:.1f}%)")
        report_lines.append(
            f"Neutral/lawful (no action): {grand_total - grand_flagged}  "
            f"({(grand_total - grand_flagged)/grand_total*100:.1f}%)"
        )

    report_text = "\n".join(report_lines)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)

    if grand_total:
        print(f"Flagged for review: {grand_flagged}/{grand_total} ({grand_flagged/grand_total*100:.1f}%)")
    print(f"Full structured report written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()