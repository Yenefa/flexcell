#!/usr/bin/env python3
"""Retire or revise an entry from what actually happened, not from what was hoped.

THE MASTER GOAL'S FIFTH STEP, AND THE HALF THAT WAS MISSING
    "Record how it was used afterwards: which task retrieved it, what action changed,
    what the result was. REVISE OR RETIRE the experience based on the actual result."

    This branch could record all three (ledger.py) and could compute the verdict
    (effect_of -> used_harmful), and then did NOTHING with it. An entry that made a run
    worse stayed ACTIVE and kept being retrievable. Recording harm without acting on it
    is a report, not a loop.

THE THREE TRANSITIONS, AND WHAT EACH REQUIRES
    RETIRE   the entry was applied and at least one run got WORSE. Requires the
             application count so a single retrieval is not mistaken for a trial.
    REVISE   a newer version exists with better evidence. Delegates to curate.admit,
             which owns supersede/merge; this module does not re-implement that.
    KEEP     anything else, including used_helpful and never_used. Silence is not
             evidence of harm, so an unused entry is not retired.

APPEND-ONLY
    Retiring writes a new RETIRED version that points at its parent, and appends an
    event. The harmful version stays on disk: the reason a lesson was withdrawn is part
    of what the repository knows.
"""
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import curate  # noqa: E402
import ledger  # noqa: E402
import schema  # noqa: E402
import store  # noqa: E402

STORE = os.path.join(WT, "evolution", "experience", "records_v2.jsonl")
LEDGER = os.path.join(WT, "evolution", "experience", "usage_ledger.jsonl")

# How many independent APPLIED events must exist before harm is actionable. One is a
# single observation, and this repository's own review found single observations
# mis-attributed three times out of four.
MIN_TRIALS = 1


def superseded_ids(rows):
    """Entry ids that some later record names as its parent.

    WHY THIS IS NEEDED: entry_id is the digest of the body, and the body includes
    version.status, so an entry that goes CANDIDATE -> ACTIVE -> RETIRED gets a NEW id at
    every transition. The old records stay in the store (append-only) and still say
    ACTIVE. A review that walks records by status alone therefore keeps seeing the
    ACTIVE ancestor forever and re-retires it on every pass - which is exactly the
    double-retirement this function prevents.
    """
    out = set()
    for row in rows:
        parent = (row.get("version") or {}).get("parent_entry_id")
        if parent:
            out.add(parent)
        for p in (row.get("version") or {}).get("supersedes") or []:
            out.add(p)
    return out


def latest(rows, entry_id):
    """The newest record on this lineage, following parent links forward."""
    children = {}
    for row in rows:
        parent = (row.get("version") or {}).get("parent_entry_id")
        if parent:
            children.setdefault(parent, []).append(row)
    current = entry_id
    seen = {entry_id}
    while True:
        nxt = children.get(current)
        if not nxt:
            return current, next((r for r in rows if r.get("entry_id") == current), None)
        # a lineage may branch; the last written child wins, which matches append order
        current = nxt[-1].get("entry_id")
        if current in seen:
            return current, None
        seen.add(current)


def review(store_path=STORE, ledger_path=LEDGER, min_trials=MIN_TRIALS,
           acceptance=None, source_task=None, measure=False):
    """Report what should happen to every ACTIVE entry.

    Two independent questions, and the answer is the WORSE of them:
      * the ledger - was it applied, and did any run get worse?  (harm -> RETIRE)
      * a fresh measurement - is the record narrower than what is now measured?
        (a stale scope -> REVISE)

    'measure' is opt-in because re-running the reuse instrument over the whole archive is
    slow and needs a source task; the default review stays a pure ledger read. When it is
    off the REVISE branch is not evaluated at all rather than reported as "not stale", which
    would be a claim the review had not checked.
    """
    rows = store.read(store_path)
    summary = ledger.summary(ledger_path)
    superseded = superseded_ids(rows)
    out = []
    for row in rows:
        if (row.get("version") or {}).get("status") != "ACTIVE":
            continue
        if row.get("entry_id") in superseded:
            # A later version supersedes this record (activation or retirement). The old
            # record keeps saying ACTIVE because the store is append-only; the lineage is
            # what says otherwise.
            continue
        eid = row.get("entry_id")
        rec = summary.get(eid) or {}
        effect = ledger.effect_of(ledger_path, eid)
        applied = rec.get("applied", 0)
        decision, why = "KEEP", "no harm recorded"
        scope = None
        if effect == "used_harmful" and applied >= min_trials:
            decision = "RETIRE"
            why = ("applied %d time(s) and at least one outcome was WORSE"
                   % applied)
        elif rec.get("retired"):
            decision, why = "RETIRE", "already retired by an earlier pass"
        elif measure:
            # HARM OUTRANKS STALENESS: an entry that made a run worse is retired whatever
            # its measured scope says, because a wider scope makes harm worse, not better.
            scope = stale_scope(row, acceptance=acceptance, source_task=source_task)
            if scope["stale"]:
                decision = "REVISE"
                why = ("the record lists %s but a fresh measurement reaches %s"
                       % (scope["recorded"], scope["measured"]))
        out.append({"entry_id": eid, "label": (row.get("version") or {}).get("label"),
                    "effect": effect, "applied": applied, "helpful": rec.get("helpful", 0),
                    "harmful": rec.get("harmful", 0), "decision": decision, "why": why,
                    "scope": scope})
    return out


def retire(entry_id, reason, store_path=STORE, ledger_path=LEDGER,
           recorded_by="lifecycle.retire"):
    """Append a RETIRED successor for one ACTIVE entry. Never rewrites history."""
    rows = store.read(store_path)
    matches = [r for r in rows if r.get("entry_id") == entry_id]
    if not matches:
        raise schema.EntryError("no such entry: %r" % (entry_id,))
    current = matches[-1]
    if (current.get("version") or {}).get("status") != "ACTIVE":
        raise schema.EntryError("only an ACTIVE entry can be retired; %r is %r"
                                % (entry_id, (current.get("version") or {}).get("status")))
    successor = json.loads(json.dumps(current))
    for key in ("prev_sha256", "chain_sha256", "record_sha256"):
        successor.pop(key, None)
    successor["version"] = dict(current["version"], status="RETIRED",
                                parent_entry_id=entry_id,
                                retired_reason=reason,
                                retired_by=recorded_by)
    successor["entry_id"] = schema.digest(schema._body(successor))
    successor["record_sha256"] = schema.digest(
        {k: v for k, v in successor.items() if k != "record_sha256"})
    problems = schema.validate(successor)
    if problems:
        raise schema.EntryError("refusing to retire into an invalid entry: %s" % problems)
    store.append(store_path, successor)
    ledger.append(ledger_path, entry_id, "RETIRED", detail=reason,
                  recorded_by=recorded_by)
    return successor


def stale_scope(entry, acceptance=None, source_task=None):
    """Has the MEASURED scope of this entry grown since it was activated?

    WHY THIS IS A REVISE AND NOT A RE-ACTIVATION: measured_families is a SNAPSHOT taken at
    activation. The reuse instrument can be re-run at any time, and when it finds a family
    the record does not list, the live entry is quietly narrower than what has been measured
    about it - retrieval withholds the lesson from a family it demonstrably fixes. The
    measurement is right and the record is out of date.

    Returns {"stale": bool, "recorded": [...], "measured": [...], "added": [...]}.
    A consumer with no callable binding measures nothing, and that is NOT staleness: it is
    the instrument saying it cannot see this entry. Reporting it as stale would revise a
    record on the strength of a blind spot.
    """
    import reuse
    recorded = set(entry.get("measured_families") or []) | {entry.get("task_family")}
    measured = reuse.measure_for_entry(entry, source_task=source_task,
                                       acceptance=acceptance)
    if not measured.get("families_with_fixes") and measured.get("why"):
        return {"stale": False, "recorded": sorted(f for f in recorded if f),
                "measured": [], "added": [],
                "why": measured["why"]}
    fresh = set(measured["families_with_fixes"])
    added = sorted(fresh - recorded)
    return {"stale": bool(added), "recorded": sorted(f for f in recorded if f),
            "measured": sorted(fresh), "added": added,
            "why": ("the recorded scope is narrower than a fresh measurement"
                    if added else "the record already covers the measured scope")}


def revise(entry_id, store_path=STORE, ledger_path=LEDGER, acceptance=None,
           source_task=None, recorded_by="lifecycle.revise"):
    """Append a successor whose measured scope matches a fresh measurement.

    THE TRANSITION THIS MODULE PROMISED AND DID NOT HAVE. Its docstring lists three:
    RETIRE, REVISE, KEEP. Only two existed. REVISE is the one that matters when the record
    is narrower than the measurement - the entry is not harmful (so RETIRE is wrong) and it
    is not fine (so KEEP is wrong). DGM's point is that a version evolves when evidence
    changes, and an ACTIVATION snapshot is evidence that goes stale.

    Only measured_families changes. The lesson, its conditions and its suggested action are
    what was reviewed and are not this function's to alter: a revision that could rewrite
    the lesson would be a second, unreviewed activation wearing a version bump.
    """
    rows = store.read(store_path)
    matches = [r for r in rows if r.get("entry_id") == entry_id]
    if not matches:
        raise schema.EntryError("no such entry: %r" % (entry_id,))
    current = matches[-1]
    if (current.get("version") or {}).get("status") != "ACTIVE":
        raise schema.EntryError("only an ACTIVE entry can be revised; %r is %r"
                                % (entry_id, (current.get("version") or {}).get("status")))
    scope = stale_scope(current, acceptance=acceptance, source_task=source_task)
    if not scope["stale"]:
        raise schema.EntryError("nothing to revise: " + scope["why"])
    successor = json.loads(json.dumps(current))
    for key in ("prev_sha256", "chain_sha256", "record_sha256"):
        successor.pop(key, None)
    # measured_families is stored WITHOUT the entry's own family: task_family already says
    # where it was learned, and repeating it here would make the two fields disagree the
    # moment one of them changed.
    successor["measured_families"] = sorted(set(scope["measured"])
                                            - {current.get("task_family")})
    successor["version"] = dict(current["version"], parent_entry_id=entry_id,
                                revised_reason=scope["why"],
                                revised_added=scope["added"],
                                revised_by=recorded_by)
    successor["entry_id"] = schema.digest(schema._body(successor))
    successor["record_sha256"] = schema.digest(
        {k: v for k, v in successor.items() if k != "record_sha256"})
    problems = schema.validate(successor)
    if problems:
        raise schema.EntryError("refusing to revise into an invalid entry: %s" % problems)
    store.append(store_path, successor)
    ledger.append(ledger_path, entry_id, "REVISED",
                  detail={"added_families": scope["added"],
                          "measured": scope["measured"]},
                  recorded_by=recorded_by)
    return successor


def apply(store_path=STORE, ledger_path=LEDGER, dry_run=False, min_trials=MIN_TRIALS):
    """Run the review and carry out every RETIRE. Returns the decisions taken."""
    decisions = review(store_path, ledger_path, min_trials)
    done = []
    for d in decisions:
        if d["decision"] != "RETIRE":
            continue
        if dry_run:
            done.append(dict(d, written=False))
            continue
        # A second pass must be idempotent. The check is on the LINEAGE, not on the
        # entry_id: entry_id changes at every transition, so looking for a RETIRED
        # record with the same id would never find one and the pass would append another
        # retirement each time.
        rows = store.read(store_path)
        _latest_id, head = latest(rows, d["entry_id"])
        if head is not None and (head.get("version") or {}).get("status") == "RETIRED":
            done.append(dict(d, written=False, why="already retired"))
            continue
        retire(d["entry_id"], d["why"], store_path, ledger_path)
        done.append(dict(d, written=True))
    return {"reviewed": len(decisions), "retired": [d for d in done if d.get("written")],
            "decisions": decisions}


def main(argv=None):
    argv = argv or sys.argv[1:]
    if argv and argv[0] == "review":
        print(json.dumps(review(argv[1] if len(argv) > 1 else STORE,
                                argv[2] if len(argv) > 2 else LEDGER), indent=2))
        return 0
    if argv and argv[0] == "apply":
        result = apply(dry_run="--dry-run" in argv)
        print(json.dumps(result, indent=2))
        return 0
    print("usage: lifecycle.py review [store] [ledger] | lifecycle.py apply [--dry-run]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
