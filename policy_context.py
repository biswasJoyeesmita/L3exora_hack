"""
policy_context.py
Defines a "policy context" — a record representing a specific government
bill/rule/policy. Every piece of monitored content gets tagged to one of
these, so you can report "here's what people are saying about Bill X"
rather than just a flat, context-less stream of comments.

This is intentionally simple (a plain dict-based registry) — no database
needed for a hackathon prototype. Swap for a real DB later if needed.
"""

import json
import os

POLICIES_PATH = "policies.json"


def load_policies() -> dict:
    """Returns {policy_id: policy_dict}."""
    if not os.path.exists(POLICIES_PATH):
        raise FileNotFoundError(f"{POLICIES_PATH} not found.")
    with open(POLICIES_PATH, encoding="utf-8") as f:
        return json.load(f)


def get_policy(policy_id: str) -> dict:
    policies = load_policies()
    if policy_id not in policies:
        raise KeyError(f"No policy found with id '{policy_id}'. Available: {list(policies.keys())}")
    return policies[policy_id]


if __name__ == "__main__":
    policies = load_policies()
    print(f"Loaded {len(policies)} policy context(s):\n")
    for pid, p in policies.items():
        print(f"- {pid}: {p['title']}")
        print(f"    keywords: {', '.join(p['keywords'])}")