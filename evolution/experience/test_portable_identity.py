#!/usr/bin/env python3
# A verification snapshot is a MEASUREMENT, not a fact about the lesson. Hashing it made the
# same entry differ across OS and churn 17 artifacts on CI while local freshness read zero.
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import schema  # noqa: E402
import store  # noqa: E402


def test_verification_snapshots_are_excluded_from_identity():
    base = {"entry_id": "x", "record_sha256": "y",
            "version": {"label": "E2", "status": "ACTIVE"},
            "suggested_action": "spread the landings"}
    a = dict(base); a["regression"] = {"verdict": "KEEP", "baselined": ["A", "B"]}
    b = dict(base); b["regression"] = {"verdict": "KEEP", "baselined": ["A"]}
    c = dict(base); c["misuse_check"] = {"verdict": "BLOCKED"}
    assert schema.digest(schema._body(a)) == schema.digest(schema._body(b))


def test_store_hash_and_schema_record_body_agree():
    """store._hash (chain) and schema.record_body (record_sha256) must omit the SAME fields,
    or verify_chain rejects records the activation path just wrote."""
    rec = {"entry_id": "e", "version": {"status": "ACTIVE"},
           "regression": {"verdict": "KEEP", "baselined": ["A"]},
           "misuse_check": {"verdict": "BLOCKED"}, "record_sha256": "old"}
    body = {k: v for k, v in rec.items()
            if k not in ("prev_sha256", "chain_sha256", "record_sha256")}
    # _hash applies its own exclusions on top of the verify_chain body
    assert store._hash(body) == schema.digest(schema.record_body(rec))


def test_committed_records_have_no_platform_specific_details():
    import json
    path = os.path.join(WT, "setup", "acceptance",
                        "evobot_continual_chain_20261118", "records_v2.jsonl")
    for line in open(path, encoding="utf-8"):
        if not line.strip():
            continue
        row = json.loads(line)
        reg = row.get("regression")
        if reg is not None:
            assert "details" not in reg, row["version"]["label"]
