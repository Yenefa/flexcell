#!/usr/bin/env python3
"""ACE-style curation plus DGM-style version retention, over an append-only store.

WHAT "CURATION" HAS TO MEAN HERE, CONCRETELY
    ACE separates Generate / Reflect / Curate and treats curation as: deduplicate,
    preserve detail, and keep a record of what helped and what hurt. Applied to this
    robot stack that is four decisions, and each one has a failure mode already observed
    in this repository:

    DUPLICATE   the same lesson written twice under different words. Harmless-looking,
                and it silently doubles the weight of one observation in any count.
    SUPERSEDE   a later version of the same lesson with better parameters. DGM's lesson
                is that the parent must remain addressable: the earlier version is what
                a regression is measured against, so it is RETIRED, never deleted.
    CONFLICT    two entries make incompatible claims under the SAME condition. This is
                the case that must stop the pipeline: the reviewer of this repository
                already found one lesson that was true and whose recommended action was
                wrong, so "both are in the store" is not a resolution.
    MERGE       the same lesson, with evidence split across two runs. Detail is the
                thing worth keeping, so the merged entry carries the UNION of the
                evidence and points at both source runs. Dropping a fact to make a tidy
                entry is exactly the loss ACE warns about.

APPEND-ONLY IS NOT NEGOTIABLE
    Nothing here rewrites a line. A supersede writes a new entry that names its parent
    and appends a RETIRED event for the old one; a merge writes a new entry with the
    union of evidence. The history of what was believed, and when, survives.
"""
import json
import os
import sys
from pathlib import Path

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import ledger  # noqa: E402
import schema  # noqa: E402
import store  # noqa: E402

STORE = os.path.join(WT, "evolution", "experience", "records_v2.jsonl")
LEDGER = os.path.join(WT, "evolution", "experience", "usage_ledger.jsonl")


def _norm(text):
    return " ".join(str(text).lower().split())


def fingerprint(entry):
    """What makes two entries the SAME lesson: consumer + kind + task family + conditions.

    Deliberately excludes the wording of the lesson and the evidence. Two entries with
    the same fingerprint are candidates for merge or conflict; two entries with different
    fingerprints are different lessons even if they sound alike.
    """
    payload = {
        "action_kind": entry.get("action_kind"),
        "consumer": entry.get("consumer"),
        "task_family": entry.get("task_family"),
        "applicable_when": sorted(_norm(c) for c in entry.get("applicable_when") or []),
    }
    return schema.digest(payload)[:16]


def _params(entry):
    spec = entry.get("effect_spec") or {}
    return json.dumps(spec.get("params") or {}, sort_keys=True)


def classify(existing, new):
    """Decide what the new entry is, relative to entries already in the store.

    Returns (decision, related_entry_ids, why). Decisions are:
      ADD        no entry shares its fingerprint
      DUPLICATE  an entry shares the fingerprint AND the same parameters
      SUPERSEDE  an entry shares the fingerprint, different parameters, same direction
      CONFLICT   an entry shares the fingerprint and contradicts it
    """
    fp = fingerprint(new)
    same = [e for e in existing if fingerprint(e) == fp]
    if not same:
        return "ADD", [], "no stored entry shares this fingerprint"
    active = [e for e in same
              if (e.get("version") or {}).get("status") in ("ACTIVE", "CANDIDATE")]
    pool = active or same
    ids = [e.get("entry_id") for e in pool]
    # ORDER MATTERS. Operator is checked BEFORE parameters: two entries that apply the
    # same numeric parameters to different operators are still different changes, and
    # calling that a duplicate would file a contradiction as redundancy. (The demo's
    # first conflict attempt was mis-reported as a duplicate for exactly this reason.)
    new_operator = (new.get("effect_spec") or {}).get("operator")
    ops = {(e.get("effect_spec") or {}).get("operator") for e in pool}
    if ops and new_operator not in ops:
        return "CONFLICT", ids, ("same condition, different operators: the entries "
                                 "prescribe different kinds of change and a human "
                                 "must choose")
    if any(_params(e) == _params(new) for e in pool):
        return "DUPLICATE", ids, ("same fingerprint and same parameters; appending it "
                                  "would double-count one observation")
    return "SUPERSEDE", ids, ("same condition and operator, different parameters: a new "
                              "version of an existing lesson")


def merge_evidence(entries):
    """Union of evidence and source runs. Detail is kept, never averaged or dropped."""
    ev = {}
    runs = []
    files = []
    for e in entries:
        for k, v in (e.get("evidence") or {}).items():
            if k in ev and ev[k] != v:
                # Two different values for the same measured field is not a detail to
                # keep - it is a contradiction. Naming it beats silently picking one.
                ev.setdefault("_conflicts", {})[k] = [ev[k], v]
                continue
            ev[k] = v
        run = e.get("source_run")
        if run and run not in runs:
            runs.append(run)
        for f in e.get("evidence_files") or []:
            if f not in files:
                files.append(f)
    return ev, runs, files


def curate(entries):
    """Report on a whole store: duplicates, conflicts, superseded chains, orphans."""
    by_fp = {}
    for e in entries:
        by_fp.setdefault(fingerprint(e), []).append(e)
    report = {"entries": len(entries), "fingerprints": len(by_fp),
              "duplicates": [], "conflicts": [], "chains": [], "orphans": []}
    ids = {e.get("entry_id") for e in entries}
    for fp, group in sorted(by_fp.items()):
        if len(group) == 1:
            e = group[0]
            parent = (e.get("version") or {}).get("parent_entry_id")
            if parent and parent not in ids:
                report["orphans"].append({"entry_id": e.get("entry_id"),
                                          "missing_parent": parent})
            continue
        # A version chain is NOT a duplicate. Curation must distinguish "the same lesson
        # written twice" from "a successor of the same lesson", or a reviewed successor
        # would be filed as redundancy and its parent's retirement would look like
        # double-counting. The lineage is read from parent_entry_id / supersedes, which
        # curate.activate writes; nothing is inferred from the wording.
        ids_in_group = {e.get("entry_id") for e in group}
        linked = [e for e in group
                  if (e.get("version") or {}).get("parent_entry_id") in ids_in_group
                  or set((e.get("version") or {}).get("supersedes") or []) & ids_in_group]
        params = {_params(e) for e in group}
        if linked:
            ordered = sorted(group, key=lambda e: str((e.get("version") or {}).get("label")))
            report["chains"].append({
                "fingerprint": fp,
                "labels": [(e.get("version") or {}).get("label") for e in ordered],
                "entry_ids": [e.get("entry_id") for e in ordered],
                "statuses": [(e.get("version") or {}).get("status") for e in ordered],
                "active": [e.get("entry_id") for e in ordered
                           if (e.get("version") or {}).get("status") == "ACTIVE"],
            })
            continue
        if len(params) == 1:
            report["duplicates"].append({"fingerprint": fp,
                                         "entry_ids": [e.get("entry_id") for e in group]})
            continue
        ops = {(e.get("effect_spec") or {}).get("operator") for e in group}
        if len(ops) > 1:
            report["conflicts"].append({"fingerprint": fp,
                                        "entry_ids": [e.get("entry_id") for e in group],
                                        "operators": sorted(o for o in ops if o)})
            continue
        ordered = sorted(group, key=lambda e: str((e.get("version") or {}).get("label")))
        report["chains"].append({
            "fingerprint": fp,
            "labels": [(e.get("version") or {}).get("label") for e in ordered],
            "entry_ids": [e.get("entry_id") for e in ordered],
            "statuses": [(e.get("version") or {}).get("status") for e in ordered],
            "active": [e.get("entry_id") for e in ordered
                       if (e.get("version") or {}).get("status") == "ACTIVE"],
        })
    return report


def admit(new, store_path=STORE, ledger_path=LEDGER, dry_run=False):
    """Try to add one entry. Returns (decision, payload). Refuses to write on CONFLICT."""
    existing = store.read(store_path)
    for e in existing:
        problems = schema.validate(e)
        if problems:
            raise schema.EntryError("store already holds an invalid entry %r: %s"
                                    % (e.get("entry_id"), problems))
    decision, related, why = classify(existing, new)
    payload = {"decision": decision, "related": related, "why": why,
               "entry_id": new.get("entry_id")}
    if decision == "DUPLICATE":
        payload["written"] = False
        return decision, payload
    if decision == "CONFLICT":
        payload["written"] = False
        payload["needs"] = "a human decision: two entries prescribe different changes"
        return decision, payload

    to_write = dict(new)
    if decision == "SUPERSEDE":
        parents = [e for e in existing if e.get("entry_id") in related]
        ev, runs, files = merge_evidence(parents + [new])
        to_write["evidence"] = ev
        to_write["evidence_files"] = files
        to_write["version"] = dict(to_write["version"],
                                   parent_entry_id=related[0],
                                   supersedes=related)
        to_write["entry_id"] = schema.digest(schema._body(to_write))
        to_write["record_sha256"] = schema.digest(
            {k: v for k, v in to_write.items() if k != "record_sha256"})
        payload["supersedes"] = related
        payload["merged_evidence_keys"] = sorted(ev)
        payload["merged_source_runs"] = runs
    problems = schema.validate(to_write)
    if problems:
        raise schema.EntryError("refusing to write an invalid entry: %s" % problems)
    payload["written"] = not dry_run
    if not dry_run:
        store.append(store_path, to_write)
        if decision == "SUPERSEDE":
            for pid in related:
                ledger.append(ledger_path, pid, "RETIRED", detail=why,
                              recorded_by="curate.admit")
        ledger.append(ledger_path, to_write["entry_id"], "RETRIEVED",
                      consumer=to_write.get("consumer"),
                      detail="admitted to the store", recorded_by="curate.admit")
    return decision, payload


def activate(candidate_id, validation, store_path=STORE, ledger_path=LEDGER,
             label=None, gate=True, acceptance=None, known_path=None,
             measured_families=None):
    """Promote a CANDIDATE to ACTIVE by APPENDING its successor, never by rewriting it.

    WHY NOT EDIT IN PLACE: the store is hash-chained, so a rewrite would either break the
    chain (and the retrieval gate would then refuse the whole store) or require
    recomputing the chain for every later record, which is the tampering the chain exists
    to detect. Appending keeps both the candidate and the review history addressable,
    which is also what makes a regression attributable to a specific version.

    The validation block comes from the caller and must name a reviewer: an entry that
    promotes itself is exactly what the master goal forbids.
    """
    if (validation or {}).get("review_verdict") not in ("ACCEPT", "REJECT"):
        raise schema.EntryError("activation needs an explicit review verdict")
    if not (validation or {}).get("reviewed_by"):
        raise schema.EntryError("activation needs a named reviewer")
    rows = store.read(store_path)
    gate_result = None
    matches = [r for r in rows if r.get("entry_id") == candidate_id]
    if not matches:
        raise schema.EntryError("no such entry in the store: %r" % (candidate_id,))
    cand = matches[-1]
    if (cand.get("version") or {}).get("status") == "ACTIVE":
        raise schema.EntryError("entry is already ACTIVE: %r" % (candidate_id,))
    # REGRESSION BEFORE ACTIVATION. A reviewer approving an entry says the entry is
    # justified; it does not say the stack still works. The master goal requires the
    # regression check to decide whether an update is KEPT, so an ACCEPT alone is not
    # enough to activate: the gate must return KEEP, and anything else leaves the
    # candidate on disk unreviewed-but-inert rather than live.
    # A REJECT verdict needs no gate: it appends a REJECTED successor so the failed
    # branch stays on disk (DGM), and nothing becomes live. The gate applies only to the
    # decision that would make the entry ACTIVE.
    if gate and validation["review_verdict"] == "ACCEPT":
        import misuse
        import regression
        gate_result = regression.gate_activation(cand, validation,
                                                 acceptance=acceptance,
                                                 known_path=known_path)
        if not gate_result["activate"]:
            raise schema.EntryError("regression gate refused activation: "
                                    + gate_result["why"])
        # MISUSE BEFORE ACTIVATION (master goal step 4). Regression asks "do old tasks
        # still pass"; it cannot ask "does this entry fire where it says it must not".
        # An entry with a disclaimer nobody tested is not safe just because the tests it
        # did run are green, so UNPROBED is refused exactly like MISUSABLE.
        misuse_result = misuse.check(cand)
        gate_result = dict(gate_result, misuse=misuse_result)
        if misuse_result["verdict"] != "BLOCKED":
            raise schema.EntryError(
                "misuse check refused activation: %s (%s)"
                % (misuse_result["verdict"], misuse_result["why"]))
    successor = json.loads(json.dumps(cand))
    # The MEASURED cross-family scope, recorded on the version that becomes live.
    # WHY IT IS WRITTEN HERE AND NOT LEFT IN A REPORT: retrieval gates on the families an
    # entry claims, and until this field existed it claimed only the one it was learned in.
    # The reuse audit measured 4 of 7 fixes in two other families and retrieval withheld
    # every one of them - a measurement the delivery channel could not act on. Recording it
    # at activation is what makes the measurement load-bearing.
    if measured_families is not None:
        successor["measured_families"] = sorted(set(measured_families)
                                                - {successor.get("task_family")})
    for key in ("prev_sha256", "chain_sha256", "record_sha256"):
        successor.pop(key, None)
    successor["validation"] = dict(validation)
    successor["version"] = dict(cand["version"],
                                status=("ACTIVE" if validation["review_verdict"] == "ACCEPT"
                                        else "REJECTED"),
                                label=label or cand["version"].get("label"),
                                parent_entry_id=candidate_id)
    if gate_result is not None:
        successor["regression"] = gate_result["regression"]
        if gate_result.get("misuse") is not None:
            successor["misuse_check"] = {
                "verdict": gate_result["misuse"]["verdict"],
                "probed": len(gate_result["misuse"]["probed"]),
                "why": gate_result["misuse"]["why"],
            }
    successor["entry_id"] = schema.digest(schema._body(successor))
    successor["record_sha256"] = schema.digest(
        {k: v for k, v in successor.items() if k != "record_sha256"})
    problems = schema.validate(successor)
    if problems:
        raise schema.EntryError("refusing to activate an invalid entry: %s" % problems)
    store.append(store_path, successor)
    ledger.append(ledger_path, candidate_id,
                  "RETIRED" if successor["version"]["status"] == "ACTIVE" else "REJECTED",
                  detail="superseded by %s (%s)" % (successor["entry_id"],
                                                    successor["version"]["status"]),
                  recorded_by="curate.activate")
    return successor


def main(argv=None):
    argv = argv or sys.argv[1:]
    if argv and argv[0] == "report":
        entries = store.read(argv[1] if len(argv) > 1 else STORE)
        print(json.dumps(curate(entries), indent=2))
        return 0
    if argv and argv[0] == "admit":
        doc = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
        decision, payload = admit(doc, dry_run="--dry-run" in argv)
        print(json.dumps(payload, indent=2))
        return 0 if decision in ("ADD", "SUPERSEDE") else 1
    print("usage: curate.py report [store] | curate.py admit <entry.json> [--dry-run]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
