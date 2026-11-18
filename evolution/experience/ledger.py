#!/usr/bin/env python3
"""The usage ledger: which entry was retrieved, whether it was applied, and what happened.

WHY A LEDGER AND NOT A COUNTER
    The master goal's third "continual" criterion is that an update must affect later
    behaviour. A store that records only what was learned cannot show that; it shows
    storage. Three separate facts have to be recorded against the SAME entry, and they
    are not the same event:
      RETRIEVED  the entry was offered to a consumer (it may have been ignored)
      APPLIED    the consumer's behaviour actually changed because of it
      OUTCOME    the run that followed was better, worse, or unchanged

    "Retrieved" alone is the number that made an earlier round look like it worked when
    it did not: one lesson was retrieved for every task and changed no plan.

HELPFUL vs HARMFUL IS RECORDED PER ENTRY, NOT PER RUN
    An entry that is applied and makes a run worse is not merely useless - it is
    dangerous, and it must be visible as harmful so it can be retired. Recording only
    "used" would let a harmful entry accumulate a clean usage count.

APPEND-ONLY. A ledger line is never edited; a correction is a new line. That keeps the
sequence auditable: the last line for an entry is its current state, and the history of
how it got there is still there.
"""
import hashlib
import json
import os
from pathlib import Path

# REVISED is a TRANSITION, not an outcome: the entry stayed live and its measured scope
# was corrected. Keeping it out of the outcome vocabulary matters - counting a revision as
# a "helpful use" would credit an entry for a bookkeeping change, and counting it as harmful
# would retire an entry that was doing exactly what the new measurement says it does.
EVENTS = ("RETRIEVED", "APPLIED", "OUTCOME", "RETIRED", "REJECTED", "REVISED")
OUTCOMES = ("IMPROVED", "UNCHANGED", "WORSE", "UNKNOWN")


class LedgerError(ValueError):
    """A malformed ledger event. Refused rather than coerced."""


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def append(path, entry_id, event, run_id=None, consumer=None, outcome=None,
           detail=None, changed=None, recorded_by=None):
    """Append one event. Returns the stored line."""
    if event not in EVENTS:
        raise LedgerError("unknown event %r; expected one of %s" % (event, EVENTS))
    if outcome is not None and outcome not in OUTCOMES:
        raise LedgerError("unknown outcome %r; expected one of %s" % (outcome, OUTCOMES))
    if not entry_id:
        raise LedgerError("entry_id is required: an unattributed event is not evidence")
    # APPLIED and OUTCOME must name the run they describe. Without a run id the event
    # cannot be tied to a measurement, and an untied event is exactly the "stored but
    # never used" ambiguity this file exists to remove.
    if event in ("APPLIED", "OUTCOME") and not run_id:
        raise LedgerError("%s requires a run_id" % event)
    line = {"event": event, "entry_id": entry_id, "run_id": run_id,
            "consumer": consumer, "outcome": outcome, "detail": detail,
            "changed": changed, "recorded_by": recorded_by}
    line["line_sha256"] = _sha(line)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(line, sort_keys=True) + "\n")
    return line


def read(path):
    p = Path(path)
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def summary(path):
    """entry_id -> counters and the latest outcome. Absent entry means never retrieved."""
    out = {}
    for row in read(path):
        eid = row.get("entry_id")
        rec = out.setdefault(eid, {"retrieved": 0, "applied": 0, "outcomes": {},
                                   "last_outcome": None, "retired": False,
                                   "rejected": False, "runs": [],
                                   "unattributed_outcomes": []})
        ev = row.get("event")
        if ev == "RETRIEVED":
            rec["retrieved"] += 1
        elif ev == "APPLIED":
            rec["applied"] += 1
            if row.get("run_id"):
                rec["runs"].append(row["run_id"])
        elif ev == "OUTCOME":
            oc = row.get("outcome") or "UNKNOWN"
            # An OUTCOME must belong to a run where this entry was actually APPLIED. A
            # standalone "WORSE" line with no matching APPLIED run is either a broken writer
            # or a forged harm signal -- and lifecycle.review RETIREs on harmful > 0. Counting
            # it would let one stray line disable an entry. Keep the line VISIBLE (never delete
            # evidence) but do not let it drive a decision: report it separately instead.
            run = row.get("run_id")
            if run is not None and run in rec["runs"]:
                rec["outcomes"][oc] = rec["outcomes"].get(oc, 0) + 1
                rec["last_outcome"] = oc
            else:
                rec["unattributed_outcomes"].append(
                    {"run_id": run, "outcome": oc,
                     "why": "no APPLIED event for this entry on that run"})
        elif ev == "RETIRED":
            rec["retired"] = True
        elif ev == "REJECTED":
            rec["rejected"] = True
    for rec in out.values():
        rec["helpful"] = rec["outcomes"].get("IMPROVED", 0)
        rec["harmful"] = rec["outcomes"].get("WORSE", 0)
    return out


def effect_of(path, entry_id):
    """How this entry has actually behaved, as one of four honest states.

    never_used      retrieved zero times, or never applied
    used_no_change  applied, and every measured outcome was UNCHANGED
    used_helpful    applied, at least one IMPROVED and no WORSE
    used_harmful    applied, at least one WORSE (reported first: harm dominates)
    """
    rec = summary(path).get(entry_id)
    if not rec or rec["applied"] == 0:
        return "never_used"
    if rec["harmful"]:
        return "used_harmful"
    if rec["helpful"]:
        return "used_helpful"
    if rec["outcomes"].get("UNCHANGED"):
        return "used_no_change"
    return "never_used"


if __name__ == "__main__":
    import sys
    path = sys.argv[1]
    if len(sys.argv) > 2:
        print(json.dumps({"effect": effect_of(path, sys.argv[2]),
                          "summary": summary(path).get(sys.argv[2])}, indent=2))
    else:
        print(json.dumps(summary(path), indent=2))
