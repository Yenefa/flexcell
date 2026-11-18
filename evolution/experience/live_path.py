#!/usr/bin/env python3
"""Is the continual chain connected to the path that actually plans a robot run?

THE GAP THIS EXISTS FOR
    Everything up to now is connected INSIDE the chain's own harness: an entry is generated,
    reviewed, gated, delivered, retrieved, applied to an archived run, and recorded. The demo
    proves that chain works. It does not prove the chain is where a plan is made.

    It is not. There are TWO stores with TWO schemas:

        evolution/experience/records.jsonl                     <- the live path reads this
            lesson, validated, provenance_verified, record_sha256, failure_class, ...

        setup/acceptance/evobot_continual_chain_.../records_v2.jsonl   <- the chain writes this
            entry_id, suggested_action, consumer, action_kind, version, validation, ...

    and zero lessons appear in both. So the chain's ACTIVE entries are invisible to
    experiments/baselines/baseline_c.py, which is the code that hands experience to the
    planner for a real run. The loop is correct and unplugged.

WHY THIS IS WORTH MEASURING RATHER THAN JUST FIXING
    Wiring it means choosing which schema wins, and that choice has a cost either way:

        write v2 into the live store   the live retrieval's filters (provenance_verified,
                                       review ledger keyed by record_sha256) do not exist in
                                       v2, so the live path would retrieve NOTHING - a
                                       fail-closed filter doing its job
        teach the live path v2         it then needs the v2 review verdict and the lineage
                                       status, which is real work and changes the file that a
                                       frozen baseline experiment reads

    Neither is a one-line change, and picking one silently would be the kind of decision that
    should be visible. So this module states the gap with numbers and names the two options;
    it does not pretend the loop closes.

WHAT IT REPORTS
    active_entries            how many ACTIVE entries the chain holds
    visible_to_live_path      how many of them the live retrieval filter would admit
    by_reason                 why each invisible one is invisible
    options                   the two ways to close it, with what each costs
"""
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import store  # noqa: E402

LIVE_STORE = os.path.join(WT, "evolution", "experience", "records.jsonl")
LIVE_LEDGER = os.path.join(WT, "evolution", "experience", "review_ledger.jsonl")
CHAIN_STORE = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118",
                           "records_v2.jsonl")


def _live_verdicts(path):
    """record_sha256 -> latest verdict, exactly as the live path reads it."""
    if not os.path.exists(path):
        return {}
    out = {}
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        out[entry.get("record_sha256")] = entry.get("verdict")
    return out


def live_filter_admits(record, verdicts):
    """Would baseline_c.retrieve() let this record through? (None, reason) when not.

    Reproduces the live filter rather than guessing at it: provenance_verified must be True
    AND the review ledger must hold an explicit ACCEPT for the record's own digest.
    """
    if record.get("provenance_verified") is not True:
        return False, "no provenance_verified"
    digest = record.get("record_sha256")
    if verdicts.get(digest) != "ACCEPT":
        return False, "no independent ACCEPT in the review ledger"
    return True, None


def report(live_store=None, live_ledger=None, chain_store=None):
    """Count the chain's ACTIVE entries that the live planning path can actually see."""
    live_store = live_store or LIVE_STORE
    live_ledger = live_ledger or LIVE_LEDGER
    chain_store = chain_store or CHAIN_STORE
    verdicts = _live_verdicts(live_ledger)
    live_rows = store.read(live_store)
    live_lessons = {str(r.get("lesson") or "") for r in live_rows}
    chain_rows = [r for r in store.read(chain_store)
                  if (r.get("version") or {}).get("status") == "ACTIVE"]
    by_reason, visible, detail = {}, 0, []
    for row in chain_rows:
        # The chain record is v2; hand it to the v1 filter unchanged. That is the honest
        # test: if the live path cannot read the record AS IT IS, it is not connected.
        admits, why = live_filter_admits(row, verdicts)
        text = str(row.get("suggested_action") or "")
        in_store = text and text in live_lessons
        if admits and in_store:
            visible += 1
            detail.append({"entry": (row.get("version") or {}).get("label"),
                           "visible": True})
            continue
        if not admits:
            reason = why
        else:
            reason = "admitted by the filter but absent from the live store"
        by_reason[reason] = by_reason.get(reason, 0) + 1
        detail.append({"entry": (row.get("version") or {}).get("label"),
                       "visible": False, "why": reason})
    return {
        "active_entries": len(chain_rows),
        "visible_to_live_path": visible,
        "by_reason": by_reason,
        "entries": detail,
        "live_store_rows": len(live_rows),
        "chain_store": os.path.relpath(chain_store, WT),
        "live_store": os.path.relpath(live_store, WT),
        "options": [
            {"option": "write v2 records into the live store",
             "cost": ("the live retrieval needs provenance_verified, evidence_files and a "
                      "review ledger keyed by record_sha256; v2 carries none of those, so "
                      "the live filter would admit nothing - fail-closed doing its job")},
            {"option": "teach the live path to read v2",
             "cost": ("it would then need the v2 review verdict and the lineage status, and "
                      "the file it reads is the one a frozen baseline experiment uses")},
        ],
        "claim": ("the chain is correct and UNPLUGGED: its entries are invisible to the "
                  "code that hands experience to the planner for a real run. Closing that "
                  "is a schema decision with a cost, so it is reported rather than assumed"),
    }


if __name__ == "__main__":
    print(json.dumps(report(), indent=2, ensure_ascii=False))
