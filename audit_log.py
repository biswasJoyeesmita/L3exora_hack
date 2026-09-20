"""
audit_log.py
Tamper-evident audit trail for Lexora's high-severity classifications.

Every Tier 3 (Hate Speech / Incitement) and Tier 4 (Direct Threat) result
gets appended here as one link in a SHA-256 hash chain: each entry's hash
is computed over its own content PLUS the previous entry's hash. Altering,
deleting, or reordering any past entry breaks every hash after it —
verify_chain() proves this by recomputing the whole chain and reporting
exactly where it breaks, if it does.

This is intentionally a single-file, dependency-free hash chain rather than
a "real" multi-node distributed ledger — for a system like this, the
property that actually matters is non-repudiation / chain-of-custody for
evidence, and a hash chain gives you that with nothing extra to deploy,
operate, or trust. It's the same core primitive a blockchain is built on.

Storage: one JSON object per line (JSON Lines) in audit-log/tier_audit_chain.jsonl,
append-only. Never edit this file by hand, and never delete/rewrite past
lines — see CONSTRAINTS.md.
"""

import hashlib
import json
import os
import threading
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_HERE, "audit-log")
LOG_PATH = os.path.join(LOG_DIR, "tier_audit_chain.jsonl")

GENESIS_HASH = "0" * 64  # the "previous hash" for the very first entry

_lock = threading.Lock()


def _canonical(record: dict) -> str:
    """Deterministic JSON encoding — same record always hashes the same way,
    regardless of key insertion order."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_hash(record: dict, prev_hash: str) -> str:
    payload = _canonical(record) + prev_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_all_entries() -> list:
    if not os.path.exists(LOG_PATH):
        return []
    entries = []
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                # A corrupted line is itself evidence of tampering (or disk
                # corruption) — surface it as its own entry so verify_chain()
                # can report it, rather than silently skipping it.
                entries.append({
                    "record": {"_corrupt_line": line_no, "_error": str(e)},
                    "prev_hash": None,
                    "entry_hash": None,
                })
    return entries


def get_last_hash() -> str:
    entries = _read_all_entries()
    if not entries:
        return GENESIS_HASH
    return entries[-1].get("entry_hash") or GENESIS_HASH


def append_entry(record: dict) -> dict:
    """
    record: a plain dict describing the flagged item — e.g. comment text,
    tier, tier_label, source (which classifier produced it), video_id,
    video_title, query. A "timestamp" is added automatically if not
    already present.

    Returns the full stored entry (record + prev_hash + entry_hash).
    """
    with _lock:
        os.makedirs(LOG_DIR, exist_ok=True)
        prev_hash = get_last_hash()

        entry_record = dict(record)
        entry_record.setdefault(
            "timestamp", datetime.now(timezone.utc).isoformat()
        )

        entry_hash = _compute_hash(entry_record, prev_hash)
        full_entry = {
            "record": entry_record,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
        }

        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(full_entry, sort_keys=True, ensure_ascii=False) + "\n")

        return full_entry


def verify_chain() -> dict:
    """
    Recomputes every hash in the chain from scratch and compares it to what
    was stored. Returns {"valid": True, "total_entries": N,
    "verified_through_hash": <hash>} if every link matches, or
    {"valid": False, "broken_at_index": i, "reason": "..."} at the first
    mismatch — everything from that index onward is untrusted.
    """
    entries = _read_all_entries()
    prev_hash = GENESIS_HASH

    for i, entry in enumerate(entries):
        record = entry.get("record")
        stored_prev = entry.get("prev_hash")
        stored_hash = entry.get("entry_hash")

        if record is None or stored_hash is None:
            return {
                "valid": False,
                "broken_at_index": i,
                "reason": f"Entry {i} is malformed or unreadable — the log "
                          f"file itself appears corrupted or truncated at "
                          f"this line.",
                "total_entries": len(entries),
            }

        if stored_prev != prev_hash:
            return {
                "valid": False,
                "broken_at_index": i,
                "reason": f"Entry {i}'s recorded prev_hash doesn't match the "
                          f"actual hash of the entry before it — the chain "
                          f"was reordered, or an earlier entry was altered "
                          f"after this one was written.",
                "total_entries": len(entries),
            }

        expected_hash = _compute_hash(record, prev_hash)
        if stored_hash != expected_hash:
            return {
                "valid": False,
                "broken_at_index": i,
                "reason": f"Entry {i}'s content no longer matches its stored "
                          f"hash — this record was edited after being "
                          f"logged.",
                "total_entries": len(entries),
            }

        prev_hash = stored_hash

    return {
        "valid": True,
        "total_entries": len(entries),
        "verified_through_hash": prev_hash,
    }


def get_entries(limit: int = None, offset: int = 0) -> list:
    """Most-recent-first. Pass limit=None for the full chain."""
    entries = list(reversed(_read_all_entries()))
    if limit is None:
        return entries[offset:]
    return entries[offset:offset + limit]


def get_count() -> int:
    return len(_read_all_entries())


if __name__ == "__main__":
    # Quick manual sanity check: append a couple of entries, verify, then
    # deliberately corrupt one and verify again to see it get caught.
    append_entry({"tier": 4, "tier_label": "Direct Threat", "comment": "test entry 1", "source": "manual_test"})
    append_entry({"tier": 3, "tier_label": "Hate Speech / Incitement", "comment": "test entry 2", "source": "manual_test"})
    print("Before tampering:", verify_chain())

    if os.path.exists(LOG_PATH):
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) >= 1:
            tampered = json.loads(lines[0])
            tampered["record"]["comment"] = "TAMPERED CONTENT"
            lines[0] = json.dumps(tampered, sort_keys=True) + "\n"
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines)
        print("After tampering entry 0:", verify_chain())
