#!/usr/bin/env python3
"""Seed the experience store from REAL archived failures, not invented ones.

Every record points at an archived run directory that still exists. The evidence is
copied from what the run actually logged. Nothing here is a recollection.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "evolution" / "experience"))
import store

STORE = WT / "evolution" / "experience" / "records.jsonl"
SEEDS = WT / "evolution" / "experience" / "seed_evidence.json"


def main():
    if STORE.exists():
        print("store already exists; append-only, refusing to reseed")
        return 1
    written = 0
    for s in json.loads(SEEDS.read_text(encoding="utf-8")):
        source = WT / s["source_run"]
        if not source.exists():
            print("SKIP (no archived evidence):", s["source_run"])
            continue
        rec = store.make_record(s["task_id"], s["failure_class"], s["evidence"],
                                s["lesson"], s["source_run"], s["outcome"])
        rec["validated"] = True
        rec["record_sha256"] = store._hash(
            {k: v for k, v in rec.items() if k != "record_sha256"})
        store.append(STORE, rec)
        written += 1
    ok, msg = store.verify_chain(STORE)
    print("records written:", written, "|", msg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
