#!/usr/bin/env python3
"""Turn archived failures into entry CANDIDATES automatically. No prose, no self-review.

WHAT WAS STILL MANUAL, AND WHY THAT MATTERS
    The chain this package implements could do everything except the first thing the
    master goal asks for: "extract a mechanism, turn it into OUR experience entry". The
    entry in demo_continual.py is written by hand. A pipeline whose only input is a human
    writing entries is not a continual loop - it is a form with validation on it.

    This module reads archived run artefacts and emits CANDIDATE entries. It is the
    generator half; the reviewer half is unchanged and still external.

WHAT IT WILL NOT DO
    * It never sets review_verdict=ACCEPT. Every emitted entry is NOT_REVIEWED, because
      the master goal forbids the agent that generated an experience from certifying it,
      and auto-acceptance would make every downstream gate vacuous in one line.
    * It never invents a consumer. A signature with no known consumer binding is reported
      UNROUTED with the reason, because "this stack has nowhere to put this knowledge" is
      a real finding (it is what happened to landing lessons before spread_destinations
      existed), not something to paper over with a guess.
    * It never promotes a single occurrence. MIN_OCCURRENCES exists because this
      repository has already published a lesson drawn from one run that turned out to be
      a mis-attribution.
    * It copies only MEASURED fields into evidence. A detail string is included as text,
      but the numbers come from parsed fields, so a claim can be re-derived.
"""
import glob
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import consumers  # noqa: E402
import schema  # noqa: E402

ACCEPTANCE = os.path.join(WT, "setup", "acceptance")
MIN_OCCURRENCES = 2

# signature -> the change that would address it. A signature absent from this table is
# reported UNROUTED: no module in this stack claims it can act on it.
SIGNATURES = {
    "occupied_destination": {
        "action_kind": "landing_spacing",
        "consumer": "spread_policy",
        "failure_class": "planning",
        "effect_spec": {"fixture": "t13_two_boxes_one_bin", "operator": "spread_step",
                        "params": {"step_m": 0.090, "baseline_step_m": 0.056},
                        "expect": {"changed": True}},
        "invalid_probes": [
            {"condition": "a single stage lands in the bin (nothing to separate)",
             "probe": "spread.single_stage"},
            {"condition": "the separation would push a landing outside the bin radius",
             "probe": "spread.narrow_bin"},
            {"condition": "more than two stages share one bin",
             "probe": "spread.three_in_one_bin"},
        ],
        "applicable_when": [
            "two or more stages declare the same or a near-identical landing point",
            "the failure detail names an occupied destination or state drift",
        ],
        "known_invalid_when": [
            "a single stage lands in the bin (nothing to separate)",
            "the separation would push a landing outside the bin radius",
            "more than two stages share one bin",
        ],
        "suggested_action": ("separate same-bin landing points by clearance plus the "
                             "measured landing drift"),
    },
    # unconfirmed_native is deliberately ABSENT.
    #
    # It is the largest cluster in the archive (46 of 51 failures), and the remedy this
    # repository actually implemented for it lives in recovery_driver.py's world-drift
    # branch, not in a function that can be called with a fixture. Writing an effect_spec
    # here would mean measuring a DIFFERENT function (respread) and labelling it "resume" -
    # a spec that passes while describing something the code does not do. That is the same
    # defect as a lesson delivered to a consumer that cannot express it, so the generator
    # reports this cluster NOT_READY instead. 46 failures with no runnable consumer is a
    # finding about the stack, not a gap in this script.
}


def scan(acceptance=None):
    """Every archived failure with its MEASURED fields. Nothing inferred."""
    root = acceptance or ACCEPTANCE
    out = []
    for path in glob.glob(os.path.join(root, "evobot*", "**", "task*.out"),
                          recursive=True):
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if "RESULT " not in text:
            continue
        try:
            res = json.loads(text.split("RESULT ", 1)[1])
        except ValueError:
            continue
        if res.get("error_code") in (0, None):
            continue
        out.append({"path": os.path.relpath(path, root),
                    "error_code": res.get("error_code"),
                    "detail": str(res.get("detail") or ""),
                    "completed_stage_ids": res.get("completed_stage_ids") or [],
                    "outcome": res.get("outcome")})
    return out


def signature_of(failure):
    """An OBSERVABLE signature. Deliberately coarse: it groups what a reader can verify."""
    detail = failure["detail"].lower()
    if "occupied destination" in detail or "destination occupied" in detail:
        return "occupied_destination"
    if "unconfirmed" in detail or "native terminal" in detail:
        return "unconfirmed_native"
    if "state drift" in detail:
        return "state_drift"
    return "error_%s" % failure.get("error_code")


def cluster(failures):
    buckets = {}
    for f in failures:
        buckets.setdefault(signature_of(f), []).append(f)
    return buckets


def build(signature, failures, task_family="T13-conditional-two-boxes"):
    """Return (entry_or_None, reason). Refuses thin evidence and unknown consumers."""
    if len(failures) < MIN_OCCURRENCES:
        return None, ("only %d occurrence(s) of %s; need %d - a single run is a "
                      "mis-attribution risk, not a lesson"
                      % (len(failures), signature, MIN_OCCURRENCES))
    spec = SIGNATURES.get(signature)
    # (checked below, after the None case, so an unrouted signature reports as UNROUTED
    # rather than as NOT_READY - the distinction is what tells a reader whether to write
    # a consumer or write a probe)
    if spec is None:
        return None, ("UNROUTED: no consumer in this stack declares a change for %r, so "
                      "the knowledge would be stored and unable to act" % signature)
    # An entry is only emittable when BOTH halves are runnable: a measurable effect, and
    # executable probes for every condition it says it must not fire in. Without the
    # second, activation would be refused downstream anyway (misuse.py UNPROBED), so
    # emitting it here would only move the failure later and make it look like a review
    # problem instead of an incomplete generation.
    if not spec.get("effect_spec", {}).get("fixture"):
        return None, ("NOT_READY: no runnable effect_spec for %r, so the entry's effect "
                      "could only be asserted" % signature)
    if len(spec.get("invalid_probes") or []) != len(spec.get("known_invalid_when") or []):
        return None, ("NOT_READY: %d declared invalid condition(s) but %d probe(s) for %r"
                      % (len(spec.get("known_invalid_when") or []),
                         len(spec.get("invalid_probes") or []), signature))
    consumer = spec["consumer"]
    if not consumers.implemented(consumer):
        return None, ("UNROUTED: %r declares this kind but its entrypoint is missing "
                      "from this checkout" % consumer)
    # Evidence comes from PARSED FIELDS of the runs, one row per contributing run.
    evidence = {
        "occurrences": len(failures),
        "error_codes": sorted({f["error_code"] for f in failures}),
        "exemplar_detail": failures[0]["detail"][:120],
        "exemplar_run": failures[0]["path"],
        "runs_with_committed_stages": sum(1 for f in failures
                                          if f["completed_stage_ids"]),
    }
    entry = schema.make_entry(
        origin="AGENT_GENERATED",
        task_family=task_family,
        failure_class=spec["failure_class"],
        source_run=failures[0]["path"],
        evidence=evidence,
        evidence_files=sorted({f["path"] for f in failures})[:16],
        provenance_verified=False,   # nothing checked this yet; see the docstring
        applicable_when=spec["applicable_when"],
        known_invalid_when=spec["known_invalid_when"],
        invalid_probes=spec["invalid_probes"],
        suggested_action=spec["suggested_action"],
        action_kind=spec["action_kind"],
        consumer=consumer,
        effect_spec=spec["effect_spec"],
        # NOT_REVIEWED is the only status this module may produce. Auto-acceptance would
        # make the review gate, the regression gate and the misuse gate vacuous at once.
        version={"label": "auto-%s" % signature, "status": "CANDIDATE",
                 "parent_entry_id": None},
        notes="generated by postmortem.build from %d archived run(s)" % len(failures),
    )
    problems = schema.validate(entry)
    if problems:
        return None, "generated entry failed its own validation: %s" % problems
    return entry, ("%d occurrence(s), consumer %r declares %r"
                   % (len(failures), consumer, spec["action_kind"]))


def generate(acceptance=None, task_family="T13-conditional-two-boxes"):
    """Scan, cluster, build. Returns (entries, report). Never writes."""
    failures = scan(acceptance)
    buckets = cluster(failures)
    entries, report = [], {"scanned": len(failures), "signatures": {}, "entries": []}
    for sig in sorted(buckets, key=lambda s: -len(buckets[s])):
        group = buckets[sig]
        entry, why = build(sig, group, task_family=task_family)
        report["signatures"][sig] = {"occurrences": len(group), "built": entry is not None,
                                     "why": why}
        if entry is not None:
            entries.append(entry)
            report["entries"].append({"signature": sig, "entry_id": entry["entry_id"],
                                      "consumer": entry["consumer"],
                                      "occurrences": len(group)})
    return entries, report


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--acceptance")
    ap.add_argument("--out")
    ap.add_argument("--task-family", default="T13-conditional-two-boxes")
    args = ap.parse_args(argv)
    entries, report = generate(args.acceptance, args.task_family)
    print(json.dumps(report, indent=2))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(entries, indent=2) + "\n")
        print("wrote", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
