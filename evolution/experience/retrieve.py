#!/usr/bin/env python3
"""Retrieve entries that can act, for a specific consumer, and record the retrieval.

FOUR GATES, EACH ONE EARNED BY A MEASURED FAILURE
    1. CHAIN INTACT        store.verify_chain. A store whose hash chain is broken cannot
                           be trusted to say what was believed; earlier rounds refused to
                           learn from it and that refusal is kept.
    2. INDEPENDENT ACCEPT  validation.review_verdict == ACCEPT. Two provenance-verified
                           entries were retrievable before review and the review then
                           found both lessons false. "Not yet rejected" is not approval.
    3. CAPABILITY          the consumer must DECLARE the entry's action_kind. This is the
                           gate that would have prevented the original defect: a landing
                           -spot lesson offered to a planner that cannot emit coordinates
                           is refused here, before it costs a token.
    4. STATUS ACTIVE       a CANDIDATE has not been validated; a RETIRED one has been
                           superseded by a better version; a REJECTED one was refused.

WHAT RETRIEVAL DELIBERATELY DOES NOT DO
    It does not rank by keyword overlap with the instruction. That scoring was measured:
    the one actionable lesson contained no task keyword, so it could never be retrieved,
    and a control-class lesson scored on every task and displaced it. Matching is on
    structured fields (task_family, action_kind, consumer), which are declared, not guessed.

EVERY RETRIEVAL IS WRITTEN TO THE LEDGER, INCLUDING AN EMPTY ONE
    An empty retrieval is recorded as such, because "the channel was empty by
    construction" was previously indistinguishable from "no lesson was relevant".
"""
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import consumers  # noqa: E402
import ledger  # noqa: E402
import store  # noqa: E402

STORE = os.path.join(WT, "evolution", "experience", "records_v2.jsonl")
LEDGER = os.path.join(WT, "evolution", "experience", "usage_ledger.jsonl")


class RetrievalRefused(RuntimeError):
    """The store itself cannot be trusted. Distinct from 'nothing matched'."""


def superseded_ids(rows):
    """Entry ids that a later record names as its parent or as superseded.

    WHY THE GATE NEEDS THIS: entry_id is a digest of the body and the body includes
    version.status, so an entry gains a NEW id at every transition. Records are
    append-only, so after a retirement the store holds BOTH the old record that still
    says ACTIVE and the new one that says RETIRED. Gating on the record alone therefore
    kept serving the retired entry - a retirement that changes nothing observable is the
    same defect as a gate nobody runs.
    """
    out = set()
    for row in rows:
        v = row.get("version") or {}
        if v.get("parent_entry_id"):
            out.add(v["parent_entry_id"])
        for p in v.get("supersedes") or []:
            out.add(p)
    return out


def _gate(entry, consumer=None, task_family=None, superseded=None):
    """Return (ok, reason). Every reason is a statement about this entry, not a score."""
    if superseded and entry.get("entry_id") in superseded:
        return False, "superseded by a later version on this lineage"
    if (entry.get("version") or {}).get("status") != "ACTIVE":
        return False, "status is %r, not ACTIVE" % (
            (entry.get("version") or {}).get("status"),)
    if (entry.get("validation") or {}).get("review_verdict") != "ACCEPT":
        return False, "no independent ACCEPT (verdict %r)" % (
            (entry.get("validation") or {}).get("review_verdict"),)
    if consumer is not None:
        kind = entry.get("action_kind")
        if kind not in consumers.CONSUMERS.get(consumer, {}).get("action_kinds", ()):
            return False, "consumer %r does not declare %r" % (consumer, kind)
    if task_family is not None:
        # The union of where the lesson was LEARNED and where it was MEASURED to work.
        # Gating on task_family alone withheld the lesson from families it had been
        # measured to fix: the reuse audit showed 4 of 7 fixed instances sat in two other
        # families, and an exact-match gate made every one of them undeliverable. A
        # measurement the delivery channel cannot act on is a number in a document.
        families = {entry.get("task_family")} | set(entry.get("measured_families") or [])
        if task_family not in families:
            return False, ("task_family %r not in %s (learned in %r, measured in %s)"
                           % (task_family, sorted(f for f in families if f),
                              entry.get("task_family"),
                              sorted(entry.get("measured_families") or [])))
    return True, "passed all gates"


def retrieve(consumer, task_family=None, store_path=STORE, ledger_path=LEDGER,
             run_id=None, record=True, limit=5):
    """Return (entries, report). Raises RetrievalRefused when the store is untrustworthy."""
    ok, msg = store.verify_chain(store_path)
    if not ok:
        raise RetrievalRefused("experience chain is broken; refusing to learn from it: "
                               + msg)
    rows = store.read(store_path)
    superseded = superseded_ids(rows)
    kept, refused = [], []
    for e in rows:
        good, why = _gate(e, consumer=consumer, task_family=task_family,
                          superseded=superseded)
        (kept if good else refused).append({"entry_id": e.get("entry_id"), "why": why,
                                            "entry": e})
    kept.sort(key=lambda r: (str((r["entry"].get("version") or {}).get("label")),
                             str(r["entry_id"])))
    chosen = kept[:limit]
    report = {"consumer": consumer, "task_family": task_family,
              "store_records": len(rows),
              "kept": [r["entry_id"] for r in chosen],
              "refused": [{"entry_id": r["entry_id"], "why": r["why"]} for r in refused],
              "chain": msg}
    if record:
        if chosen:
            for r in chosen:
                ledger.append(ledger_path, r["entry_id"], "RETRIEVED",
                              consumer=consumer, run_id=run_id,
                              detail="offered to %s" % consumer,
                              recorded_by="retrieve.retrieve")
        else:
            # An empty retrieval is evidence too: it says the channel had nothing that
            # could act, which is different from the channel never being consulted.
            ledger.append(ledger_path, "NO_ENTRY", "RETRIEVED", consumer=consumer,
                          run_id=run_id,
                          detail="no entry passed the gates for consumer %r" % (consumer,),
                          recorded_by="retrieve.retrieve")
    return [r["entry"] for r in chosen], report


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--consumer", required=True)
    ap.add_argument("--task-family")
    ap.add_argument("--store", default=STORE)
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--run-id")
    ap.add_argument("--no-record", action="store_true")
    args = ap.parse_args(argv)
    try:
        entries, report = retrieve(args.consumer, args.task_family, args.store,
                                   args.ledger, args.run_id, not args.no_record)
    except RetrievalRefused as exc:
        print(json.dumps({"refused": str(exc)}, indent=2))
        return 1
    print(json.dumps({"report": report,
                      "entries": [{"entry_id": e["entry_id"],
                                   "action_kind": e["action_kind"],
                                   "suggested_action": e["suggested_action"],
                                   "effect_spec": e["effect_spec"]} for e in entries]},
                     indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
