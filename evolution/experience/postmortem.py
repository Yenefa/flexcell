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
import re
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
            {"condition": "the landings ALREADY meet the spacing contract",
             "probe": "spacing.already_satisfied"},
        ],
        "applicable_when": [
            "two or more stages declare the same or a near-identical landing point",
            "the failure detail names an occupied destination or state drift",
        ],
        "known_invalid_when": [
            "a single stage lands in the bin (nothing to separate)",
            "the separation would push a landing outside the bin radius",
            "more than two stages share one bin",
            "the landings ALREADY meet the spacing contract",
        ],
        "suggested_action": ("separate same-bin landing points by clearance plus the "
                             "measured landing drift"),
    },
    "order_clause_violated": {
        "action_kind": "move_order",
        "consumer": "planner",
        "failure_class": "planning",
        "effect_spec": {"fixture": "t14_ordered_pair", "operator": "delivery",
                        "params": {},
                        "expect": {"delivered": True}},
        "applicable_when": [
            "the instruction fixes which object must be moved first",
            "the grading report lists an 'order' clause as failed",
        ],
        "known_invalid_when": [],
        "invalid_probes": [],
        "suggested_action": ("emit the moves in the order the instruction states; a plan "
                             "that puts the right blocks in the right bin in the wrong "
                             "order fails the order clause"),
    },
    "harness_dds_exhaustion": {
        "action_kind": "harness_config",
        "consumer": "harness",
        "failure_class": "tooling",
        "effect_spec": {"fixture": "t05_dds_harness", "operator": "harness_capacity",
                        "params": {"participant_capacity": 120, "baseline_capacity": 0},
                        "expect": {"changed": True,
                                   "applied_harness_failures_lte": 0}},
        "applicable_when": [
            "several ROS processes share one DDS domain on one host",
            "a run reports it never dispatched, with no task.out at all",
        ],
        "known_invalid_when": [
            "the participant pool already exceeds the number of nodes the launch starts",
            "the config declares no participant pool at all",
        ],
        "invalid_probes": [
            {"condition": "the participant pool already exceeds the number of nodes the "
                          "launch starts",
             "probe": "harness.capacity_already_sufficient"},
            {"condition": "the config declares no participant pool at all",
             "probe": "harness.capacity_removed"},
        ],
        "suggested_action": ("raise the DDS participant pool above the number of nodes the "
                             "launch starts; a failed launch looks like a motion bug"),
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


def held_out_batches():
    """Batches that were run to MEASURE generalization, not to develop against.

    WHY THIS EXISTS: the first version of scan() globbed every archived batch, so the
    single entry it generated drew one of its five occurrences from
    evobot_unseen_n6_20261111 - a held-out measurement batch. An experience learned
    partly from the held-out set cannot later be cited as evidence that the agent
    generalizes to the held-out set; that is the same defect as "training-set results
    passed off as unseen data", which the master goal names explicitly.

    The list is DERIVED, not hand-maintained: a batch is held-out when its
    evidence_index rung says "Generalization Tested". Deriving it means a new held-out
    batch is excluded the moment it is indexed, instead of the moment somebody remembers.

    TWO INDEPENDENT CRITERIA, because one of them can be wrong:
      1. the batch's rung says "Generalization Tested" - a LABEL, and labels drift;
      2. the batch runs an instance that is in the CURRENT strict held-out set - a FACT
         read from benchmark/held_out/public, which does not depend on anyone having
         labelled the batch correctly.
    Criterion 2 is the one that survives a mislabelled batch. It costs one directory
    listing and catches the case where a development batch quietly reuses a sealed
    instance, which is exactly how the previous v0.1 held-out set got contaminated.

    FAIL-CLOSED: if the index cannot be read this raises. Refusing to generate is
    correct here - generating from an unknown split could silently contaminate the
    held-out set, and nothing downstream would ever notice.
    """
    sys.path.insert(0, os.path.join(WT, "experiments", "baselines"))
    import evidence_index
    batches = {name for name, rung in evidence_index.RUNGS.items()
               if "Generalization Tested" in (rung or "")}
    if not batches:
        raise RuntimeError("no held-out batch found in evidence_index.RUNGS; refusing to "
                           "generate from an unclassified archive")
    return batches


# NOT \b at the end: a run directory is named HO-<12 hex>_B or _C for the B/C arms, and
# "_" is a word character, so \b fails to match exactly the paired arms that carry the
# held-out comparison. The first version used \b and silently missed every _B/_C run -
# a leak detector that cannot see half the runs it exists to catch.
SEALED_ID = re.compile(r"\bHO-[0-9a-f]{12}(?![0-9a-f])")


# Every directory under benchmark/held_out that holds instance specs. Both count: the
# "unseen_public" set is the T12/T13 unseen-task-type instances, and T13 is exactly the
# task family this chain's lesson is about. Scanning only "public" would have left the
# lesson's own instances outside the check.
HELD_OUT_DIRS = ("public", "unseen_public")


def sealed_instances():
    """Instance ids in the CURRENT strict held-out sets. Empty set if none are present."""
    out = set()
    for name in HELD_OUT_DIRS:
        d = os.path.join(WT, "benchmark", "held_out", name)
        if os.path.isdir(d):
            out |= {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(d, "*.json"))}
    return out


def cites_sealed(path, sealed):
    """True when this artefact's path names a currently sealed held-out instance."""
    if not sealed:
        return False
    return bool(set(SEALED_ID.findall(path)) & sealed)


def _clause_failures(root, excluded_names, sealed):
    """Failures recorded by the EVALUATOR, read from verdict*.json.

    WHY A THIRD CHANNEL: task.out carries what the RUNNER reported, summary.txt carries
    what the BATCH reported, and verdict.json carries what the GRADER found. An order
    clause can fail while the runner reports success - in this archive three T14 runs
    passed their first attempt and then failed the order clause on the retry. None of
    those appear in task.out, so a scanner reading only the runner's channel cannot see
    the one failure class that is purely about planning.

    Graded failures are also the only ones that cannot be self-reported, which is why they
    are worth a separate channel rather than folded into the runner's.
    """
    out, excluded = [], {}
    for path in glob.glob(os.path.join(root, "evobot*", "**", "verdict*.json"),
                          recursive=True):
        try:
            doc = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or doc.get("passed") is not False:
            continue
        clauses = [str(c) for c in (doc.get("failed_clauses") or [])]
        if not clauses:
            continue
        rel = os.path.relpath(path, root)
        batch = rel.split(os.sep)[0]
        if batch in excluded_names:
            excluded["%s:labelled_generalization_batch" % batch] = excluded.get(
                "%s:labelled_generalization_batch" % batch, 0) + 1
            continue
        if cites_sealed(rel, sealed):
            excluded["%s:sealed_instance" % batch] = excluded.get(
                "%s:sealed_instance" % batch, 0) + 1
            continue
        # An "order" clause can fail for two very different reasons and the clause name
        # alone does not say which. If only SOME of the required moves happened, the order
        # clause fails as a side effect of an incomplete run - the second move never
        # happened, so it was not out of order. Teaching a planning rule from those would
        # be teaching it from a placement failure. Only a plan whose moves happened but in
        # the WRONG SEQUENCE is an order lesson.
        order_kind = None
        for clause in (doc.get("clauses") or []):
            if not isinstance(clause, dict) or clause.get("clause") != "order":
                continue
            ev = clause.get("evidence") or {}
            required = [str(x) for x in (ev.get("required") or [])]
            observed = [str(x) for x in (ev.get("observed") or [])]
            if not required:
                order_kind = "unknown"
            elif observed[:len(required)] == required:
                order_kind = "satisfied"
            elif observed and required[:len(observed)] == observed:
                # every observed move is in the right place, but some never happened
                order_kind = "incomplete"
            elif sorted(observed) == sorted(required):
                order_kind = "reordered"
            else:
                order_kind = "mismatched"
        out.append({"path": rel, "batch": batch, "error_code": None,
                    "layer": "GRADED", "detail": "failed clause(s): " + ", ".join(clauses),
                    "clauses": clauses, "order_kind": order_kind,
                    "completed_stage_ids": [], "outcome": None})
    return out, excluded


def _console_failures(root, excluded_names, sealed):
    """Failures that never produced a task.out at all, read from summary.txt.

    WHY THIS EXISTS: scan() reads task*.out, so a run whose STACK never started has no
    task.out and is invisible to it. Five archived runs are like that, and they are the
    DDS participant-exhaustion lesson - a real defect that cost two rounds of
    misattribution ("Gazebo is unstable") precisely because the evidence channel that was
    being scanned could not contain it. A generator that can only see dispatched runs will
    keep rediscovering motion bugs and never rediscover launch bugs.

    The row shape matches scan() so downstream clustering does not special-case it. The
    distinguishing field is layer="HARNESS".
    """
    out, excluded = [], {}
    for path in glob.glob(os.path.join(root, "evobot*", "summary.txt")):
        rel = os.path.relpath(path, root)
        batch = rel.split(os.sep)[0]
        if batch in excluded_names:
            continue
        for line in open(path, encoding="utf-8", errors="replace"):
            parts = line.split()
            if len(parts) < 3 or not parts[0].startswith("s"):
                continue
            if parts[2] != "HARNESS":
                continue
            seed = parts[0]
            # The summary row says only "stack unavailable". The CAUSE is in the run's
            # stack.log, so read it: "the stack did not come up" is not a lesson, and a
            # generator that stops at the summary would file the DDS bug under "unknown".
            cause = _stack_log_cause(os.path.join(root, batch, "runs"), seed)
            detail = "stack never dispatched (%s)" % (cause or "cause not recorded")
            artifact = rel
            if cites_sealed(rel, sealed):
                excluded["%s:sealed_instance" % batch] = excluded.get(
                    "%s:sealed_instance" % batch, 0) + 1
                continue
            out.append({"path": artifact, "batch": batch, "error_code": None,
                        "layer": "HARNESS", "seed": seed, "detail": detail,
                        "completed_stage_ids": [], "outcome": None})
    return out, excluded


def _stack_log_cause(runs_dir, seed):
    """Read a HARNESS run's stack.log and name the cause, or None.

    Refuses to guess. The words it recognises are the ones the runtime actually prints;
    anything else returns None and is reported as "cause not recorded" rather than being
    filed under a convenient label.
    """
    if not os.path.isdir(runs_dir):
        return None
    hits = []
    for d in sorted(glob.glob(os.path.join(runs_dir, seed + "*"))):
        log = os.path.join(d, "stack.log")
        if not os.path.exists(log):
            continue
        try:
            text = open(log, encoding="utf-8", errors="replace").read().lower()
        except OSError:
            continue
        if "participant index" in text or "out of range" in text:
            hits.append("dds_participant")
        elif "error" in text:
            hits.append("stack_error")
    if not hits:
        return None
    return sorted(set(hits))[0]


def scan_with_report(acceptance=None, include_held_out=False):
    """Scan, and report exactly which batches were excluded and why.

    Returns (rows, excluded) where excluded maps batch -> failure count skipped.
    """
    root = acceptance or ACCEPTANCE
    excluded_names = set() if include_held_out else held_out_batches()
    sealed = set() if include_held_out else sealed_instances()
    out, excluded = [], {}
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
        rel = os.path.relpath(path, root)
        batch = rel.split(os.sep)[0]
        # two independent reasons to skip: a labelled measurement batch, or a run of an
        # instance that is currently sealed. Either one is disqualifying on its own.
        reason = ("labelled_generalization_batch" if batch in excluded_names
                  else "sealed_instance" if cites_sealed(rel, sealed) else None)
        if reason:
            key = batch if reason == "labelled_generalization_batch" else "%s:%s" % (
                batch, reason)
            excluded[key] = excluded.get(key, 0) + 1
            continue
        out.append({"path": rel,
                    "batch": batch,
                    "error_code": res.get("error_code"),
                    "layer": "EXECUTION",
                    "detail": str(res.get("detail") or ""),
                    "completed_stage_ids": res.get("completed_stage_ids") or [],
                    "outcome": res.get("outcome")})
    # Runs whose stack never came up leave no task.out, so they must be collected from a
    # different channel or they do not exist as far as this generator is concerned.
    console_rows, console_excluded = _console_failures(root, excluded_names, sealed)
    out.extend(console_rows)
    for k, v in console_excluded.items():
        excluded[k] = excluded.get(k, 0) + v
    # ... nor do the GRADER's own findings, which live in verdict.json.
    clause_rows, clause_excluded = _clause_failures(root, excluded_names, sealed)
    out.extend(clause_rows)
    for k, v in clause_excluded.items():
        excluded[k] = excluded.get(k, 0) + v
    return out, excluded


def scan(acceptance=None, include_held_out=False):
    """Every NON-held-out archived failure with its MEASURED fields. Nothing inferred."""
    return scan_with_report(acceptance, include_held_out)[0]


def signature_of(failure):
    """An OBSERVABLE signature. Deliberately coarse: it groups what a reader can verify."""
    detail = failure["detail"].lower()
    # A HARNESS-layer failure is its own kind regardless of wording: the run never
    # dispatched, so no motion or planning diagnosis applies to it. Grouping it with the
    # motion rows would let a launch bug be counted as evidence about the executor.
    if failure.get("layer") == "GRADED":
        # A graded failure is classified by the CLAUSE that failed, not by the detail
        # prose: the clause name is the machine-readable part and the prose is a summary.
        clauses = [str(c) for c in (failure.get("clauses") or [])]
        if "order" in clauses:
            # Only a genuine reordering is a planning lesson. An incomplete run fails the
            # order clause too, but its cause is elsewhere and filing it here would teach
            # the planner to fix something that was never wrong.
            kind = failure.get("order_kind")
            if kind == "reordered":
                return "order_clause_violated"
            if kind == "incomplete":
                return "incomplete_execution"
            return "order_unclassified"
        if any(c.startswith("placement:") for c in clauses):
            return "placement_clause_failed"
        return "graded_%s" % (clauses[0].split(":")[0] if clauses else "unknown")
    if failure.get("layer") == "HARNESS":
        if "participant" in detail or "domain" in detail or "socket" in detail:
            return "harness_dds_exhaustion"
        return "harness_stack_absent"
    if "occupied destination" in detail or "destination occupied" in detail:
        return "occupied_destination"
    if "unconfirmed" in detail or "native terminal" in detail:
        return "unconfirmed_native"
    if "order clause" in detail or "wrong order" in detail:
        return "order_clause_violated"
    if "state drift" in detail:
        return "state_drift"
    return "error_%s" % failure.get("error_code")


def cluster(failures):
    buckets = {}
    for f in failures:
        buckets.setdefault(signature_of(f), []).append(f)
    return buckets


def build(signature, failures, task_family="T13-conditional-two-boxes", split="dev"):
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
        # WHICH SPLIT the evidence came from. A reader who sees "held_out" here knows the
        # entry may demonstrate a mechanism but cannot support a generalization claim -
        # the instrument would have been read into the thing it measures.
        "evidence_split": split,
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
        notes="generated by postmortem.build from %d archived %s run(s)"
              % (len(failures), "HELD-OUT" if split == "held_out" else "development"),
    )
    problems = schema.validate(entry)
    if problems:
        return None, "generated entry failed its own validation: %s" % problems
    return entry, ("%d occurrence(s), consumer %r declares %r"
                   % (len(failures), consumer, spec["action_kind"]))


def generate(acceptance=None, task_family="T13-conditional-two-boxes",
             include_held_out=False, split=None):
    """Scan, cluster, build. Returns (entries, report). Never writes.

    split is "dev" (default), "held_out", or None (= dev, falling back to held_out ONLY
    when the development split yields nothing and the caller asked for it explicitly).

    The default is "dev". The reason is not squeamishness: this repository's T12/T13 task
    families exist ONLY in the held-out set, so the honest default produces ZERO entries
    and says so. Generating from held-out data is available, labelled, and never silent.
    """
    split = split or "dev"
    held_out = sorted(held_out_batches())
    failures, excluded = scan_with_report(acceptance, include_held_out=(split == "held_out"))
    buckets = cluster(failures)
    # Report BOTH numbers regardless of mode: how many failures the held-out exclusion
    # would drop, and how many this run actually dropped. Reporting only the second makes
    # a held-out run look like there was nothing to exclude, which is the opposite of true.
    _, would_exclude = scan_with_report(acceptance, include_held_out=False)
    entries, report = [], {"scanned": len(failures),
                           "split": split,
                           "excluded_held_out": excluded,
                           "held_out_would_exclude": sum(would_exclude.values()),
                           "held_out_batches": held_out,
                           "sealed_instances": len(sealed_instances()),
                           "signatures": {}, "entries": []}
    for sig in sorted(buckets, key=lambda s: -len(buckets[s])):
        group = buckets[sig]
        entry, why = build(sig, group, task_family=task_family, split=split)
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
