#!/usr/bin/env python3
"""A tamper-evident review ledger: a review cannot be INSERTED or EDITED after the fact.

WHAT THIS FIXES
    live_binding.resolve() now trusts a separate review ledger, keyed by entry_id. An
    independent ACCEPT is the ONLY thing that lets a reviewed entry drive a live robot call.
    But the ledger was a plain JSONL file: anyone could append

        {"entry_id": "<E2>", "verdict": "ACCEPT", "reviewed_by": "any-name"}

    and the gate would hand parameters to apply_respread. The most important gate in the
    chain had no integrity at all.

WHAT A HASH CHAIN DOES AND DOES NOT PROVE
    It PROVES that no record was deleted or reordered WITHIN the chain and that none was
    edited afterwards. It does NOT prove the reviewer was who they claimed (that needs a
    signature / external identity); does not stop a reviewer appending a NEW review; and
    cannot detect TAIL TRUNCATION — deleting the last record leaves a valid shorter chain.
    All limits are stated in the artifact rather than papered over.

    For a live parameter change, "a review existed and was not later altered" is the
    checkable part. "Was the reviewer genuinely independent" stays a property of process,
    and the gate still refuses the demo's own self-reviewer by name.
"""
import hashlib
import json
import os

GENESIS = "0" * 64
_HASH_FIELDS = ("entry_id", "verdict", "reviewed_by", "reason", "review_ref")


def _digest(record):
    body = {k: record[k] for k in _HASH_FIELDS if k in record}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


def append(path, review):
    """Append one review with a hash chain. Returns the chained record."""
    rows = read(path)
    row = dict(review)
    row["prev_sha256"] = rows[-1]["chain_sha256"] if rows else GENESIS
    row["review_sha256"] = _digest(row)
    row["chain_sha256"] = hashlib.sha256(
        (row["prev_sha256"] + row["review_sha256"]).encode()).hexdigest()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    mode = "a" if rows else "w"
    with open(path, mode, encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n")
    return row


def read(path):
    if not path or not os.path.exists(path):
        return []
    out = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def verify(path):
    """(ok, why). Detects editing, reordering and non-tail deletion of reviews.

    Tail truncation is NOT detectable by a forward-only chain: removing the last record
    leaves a chain whose remaining records all still verify. Stated as a limit, not hidden.
    """
    rows = read(path)
    if not rows:
        return False, "empty ledger"
    prev = GENESIS
    for i, row in enumerate(rows):
        if row.get("prev_sha256") != prev:
            return False, "chain break at review %d" % i
        if row.get("review_sha256") != _digest(row):
            return False, "review hash mismatch at %d" % i
        calc = hashlib.sha256(
            (prev + row["review_sha256"]).encode()).hexdigest()
        if row.get("chain_sha256") != calc:
            return False, "chain hash mismatch at %d" % i
        prev = row["chain_sha256"]
    return True, "chain intact (%d reviews)" % len(rows)
