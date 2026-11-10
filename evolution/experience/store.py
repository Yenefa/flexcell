#!/usr/bin/env python3
"""EvoBot evidence-backed experience store (Level 6 Learn).

DESIGN DECISION: experience records are MACHINE-GENERATED from verifier evidence, not
written by the model as prose. In the preceding FlexCell track, four framings failed to
get the model to write a usable experience note (P2 item 2 was not achieved). So the
agent is not asked to summarise itself; the pipeline records what the evaluator
measured, and the agent may only RETRIEVE it.

APPEND-ONLY: no update, no delete. Records form a hash chain, so removal or reordering
is detectable. Failure evidence is never dropped.

SCOPE GUARD: a record may describe a PLANNER-level lesson only. Anything naming an
evaluator, tolerance, threshold or world hash is refused at write time, so the
experience channel cannot be used to manufacture success.
"""
import hashlib
import json
from pathlib import Path

STORE_VERSION = "0.1.0"
FORBIDDEN_TOPICS = ["evaluator", "tolerance", "threshold", "acceptance", "world_sha",
                    "verifier", "grading", "pass_threshold"]

FAILURE_CLASSES = ["perception", "planning", "kinematics", "control", "grasp",
                   "state", "tooling", "runtime", "model", "environment", "UNKNOWN"]


def _hash(record):
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()


def _check_scope(text):
    low = (text or "").lower()
    for word in FORBIDDEN_TOPICS:
        if word in low:
            raise ValueError("experience record touches a protected topic: " + word)


def make_record(task_id, failure_class, evidence, lesson, source_run, outcome):
    """Build one record. evidence = measured facts, never a self-claim."""
    if failure_class not in FAILURE_CLASSES:
        raise ValueError("unknown failure class " + repr(failure_class))
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("evidence must be a non-empty dict of measured facts")
    _check_scope(lesson)
    _check_scope(json.dumps(evidence))
    rec = {"store_version": STORE_VERSION, "task_id": task_id,
           "failure_class": failure_class, "evidence": evidence,
           "lesson": lesson[:500], "source_run": source_run,
           "outcome": outcome, "validated": False}
    rec["record_sha256"] = _hash(rec)
    return rec


def append(path, record):
    """Append one record with a hash chain. Never overwrite, never delete."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = read(p) if p.exists() else []
    if rows and any(r.get("record_sha256") == record.get("record_sha256") for r in rows):
        raise ValueError("duplicate experience record")
    prev = rows[-1]["chain_sha256"] if rows else "0" * 64
    chained = dict(record)
    chained["prev_sha256"] = prev
    chained["chain_sha256"] = _hash(chained)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(chained, sort_keys=True) + "\n")
    return chained


def read(path):
    p = Path(path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def verify_chain(path):
    """Detect deletion, reordering or tampering of any record."""
    rows = read(path)
    prev = "0" * 64
    for i, r in enumerate(rows):
        if r.get("prev_sha256") != prev:
            return False, "chain break at record %d" % i
        # record_sha256 is computed over the record WITHOUT itself, so it must be
        # excluded from the body being re-hashed; including it makes every record
        # look tampered with.
        body = {k: v for k, v in r.items()
                if k not in ("prev_sha256", "chain_sha256", "record_sha256")}
        if r.get("record_sha256") != _hash(body):
            return False, "record hash mismatch at %d" % i
        check = dict(r)
        check.pop("chain_sha256", None)
        if r.get("chain_sha256") != _hash(check):
            return False, "chain hash mismatch at %d" % i
        prev = r["chain_sha256"]
    return True, "chain intact (%d records)" % len(rows)


if __name__ == "__main__":
    import sys
    ok, msg = verify_chain(sys.argv[1])
    print(msg)
    sys.exit(0 if ok else 1)
