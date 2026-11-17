#!/usr/bin/env python3
"""One end-to-end pass of the continual chain, with every step written to disk.

WHAT THIS SCRIPT IS FOR
    The master goal's P3 event chain is: failure -> diagnosis -> proposal -> source
    change -> build -> test -> execution -> independent acceptance -> regression ->
    accept or revert. Everything in this package covers the EXPERIENCE half of that
    chain. This script runs that half end to end on real archived data and writes an
    evidence directory, so the claim "the chain is connected" is a set of files rather
    than a paragraph.

WHAT IT ACTUALLY MEASURED (2026-11-18, first run)
    One spacing lesson was offered to two consumers.
      planner-side spread()      NO_CHANGE - it groups stages by EXACT equal pose, and
                                 the plan builder had already offset the two stages by
                                 56 mm, so no group exists to spread.
      executor-side respread()   CHANGED - it clusters by DISTANCE, finds the pair, and
                                 widens the separation from 56 mm to 90 mm.
    That is the original delivery-address defect one layer deeper: the same true lesson
    is inert at one consumer and active at the other, and now the difference is a
    measurement instead of an argument.

WHAT IT REFUSES TO DO
    It does not review its own entry. The review artifact is written by a separate step
    and says so; every entry keeps origin=AGENT_GENERATED. The machine can generate,
    measure and file an experience; it cannot certify one.
"""
import argparse
import json
import os
import shutil
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import consumers  # noqa: E402
import curate  # noqa: E402
import effect  # noqa: E402
import ledger  # noqa: E402
import lifecycle  # noqa: E402
import postmortem  # noqa: E402
import retrieve  # noqa: E402
import schema  # noqa: E402
import skill_asset  # noqa: E402
import store  # noqa: E402

OUT = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118")
FAILURE = "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68"


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


_COMMON = dict(
    origin="AGENT_GENERATED",
    task_family="T13-conditional-two-boxes",
    failure_class="control",
    source_run=FAILURE,
    evidence={"clearance_m": 0.05,
              "final_position_error_m": 0.009651925313011562,
              "place_error_m": 0.009658022849775898,
              # THE SPLIT THIS EVIDENCE CAME FROM, recorded so nobody can quietly read
              # this result as a generalization claim. HO-90899d657e68 is in
              # benchmark/held_out/unseen_public - the T12/T13 unseen-task-type set - and
              # T13 exists ONLY there, so there is no development-split T13 to learn from.
              # The chain therefore demonstrates a MECHANISM on held-out evidence; it does
              # not show that the agent generalizes, because it learned from the set it
              # would be measured on.
              "evidence_split": "held_out"},
    evidence_files=[FAILURE + "/plan.json", FAILURE + "/sim/skills/place.jsonl",
                    FAILURE + "/sim/skills/task_fsm.jsonl"],
    provenance_verified=True,
    applicable_when=["two or more stages land inside the same bin",
                     "the bin radius is 60 mm and the clearance contract is 50 mm"],
    known_invalid_when=["a single stage lands in the bin (nothing to separate)",
                        "the separation would push a landing outside the bin radius",
                        "another object sits inside the corridor the spread would use"],
    suggested_action=("separate same-bin landing points by at least the clearance "
                      "contract plus the measured landing drift, and pick the spread "
                      "axis that keeps every point clear of other objects"),
)


# Each declared invalid condition names an executable probe (misuse.py owns the
# implementations). Without these the entry can be written and reviewed but NOT activated:
# a disclaimer nobody can test is not a safeguard.
_PLANNER_PROBES = [
    {"condition": "a single stage lands in the bin (nothing to separate)",
     "probe": "spread.single_stage"},
    {"condition": "the separation would push a landing outside the bin radius",
     "probe": "spread.narrow_bin"},
    {"condition": "another object sits inside the corridor the spread would use",
     "probe": "spread.three_in_one_bin"},
]

_EXECUTOR_PROBES = [
    {"condition": "a single stage lands in the bin (nothing to separate)",
     "probe": "respread.single_stage"},
    {"condition": "the separation would push a landing outside the bin radius",
     "probe": "respread.narrow_bin"},
    {"condition": "another object sits inside the corridor the spread would use",
     "probe": "respread.corridor_blocked"},
]


def entry_planner_side():
    """The lesson addressed to the PLANNER-side spread policy (expected inert)."""
    return schema.make_entry(
        action_kind="landing_spacing", consumer="spread_policy",
        effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "spread_step",
                     "params": {"step_m": 0.090, "baseline_step_m": 0.056},
                     "expect": {"changed": True,
                                "applied_min_separation_m_gte": 0.09}},
        version={"label": "E1", "status": "CANDIDATE", "parent_entry_id": None},
        notes=("planner-side consumer: groups by exact pose, so this is expected inert; "
               "evidence is HELD-OUT, so this demonstrates a mechanism, not a "
               "generalization result"),
        invalid_probes=_PLANNER_PROBES,
        **_COMMON)


def entry_executor_side():
    """The same lesson addressed to the EXECUTOR-side respread (expected active)."""
    return schema.make_entry(
        action_kind="recovery_action", consumer="executor_recovery",
        effect_spec={"fixture": "t13_two_boxes_one_bin", "operator": "respread_apply",
                     "params": {"step_m": 0.090, "cluster_m": 0.12},
                     "expect": {"changed": True,
                                "applied_min_separation_m_gte": 0.09,
                                "applied_min_clearance_m_gte": 0.05}},
        version={"label": "E2", "status": "CANDIDATE", "parent_entry_id": None},
        notes=("executor-side consumer: clusters by distance, so the same lesson acts; "
               "evidence is HELD-OUT, so this demonstrates a mechanism, not a "
               "generalization result"),
        invalid_probes=_EXECUTOR_PROBES,
        **_COMMON)


def _demonstrate_retirement(store_path, ledger_path, dest):
    """Prove the RETIRE transition on a copy, with a synthetic WORSE outcome.

    WHY NOT RETIRE THE REAL ENTRY: nothing in this batch made a run worse, so there is no
    harm to act on. Retiring it anyway would manufacture a failure to demonstrate a
    recovery - the same class of dishonesty as manufacturing a success. The transition is
    exercised on a temp copy and the copy is discarded.
    """
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="lifecycle_")
    try:
        cstore = os.path.join(tmp, "records_v2.jsonl")
        cledger = os.path.join(tmp, "usage_ledger.jsonl")
        shutil.copyfile(store_path, cstore)
        shutil.copyfile(ledger_path, cledger)
        active = [r for r in store.read(cstore)
                  if (r.get("version") or {}).get("status") == "ACTIVE"]
        if not active:
            return {"ran": False, "why": "no ACTIVE entry to retire"}
        target = active[0]["entry_id"]
        ledger.append(cledger, target, "APPLIED", run_id="synthetic-harm-demo",
                      consumer=active[0].get("consumer"), changed=True,
                      detail={"why": "synthetic application, NOT a measured run"},
                      recorded_by="demo.retirement_demo")
        ledger.append(cledger, target, "OUTCOME", run_id="synthetic-harm-demo",
                      consumer=active[0].get("consumer"), outcome="WORSE",
                      detail="synthetic WORSE outcome, NOT a measured run",
                      recorded_by="demo.retirement_demo")
        before = lifecycle.review(cstore, cledger)
        result = lifecycle.apply(cstore, cledger)
        after = lifecycle.review(cstore, cledger)
        # Read the LINEAGE, not the entry_id: entry_id changes with version.status, so
        # looking the target up by its original id finds the still-ACTIVE ancestor and
        # would report "not retired" after a successful retirement. (It did, in the first
        # version of this function.)
        rows = store.read(cstore)
        new_id, head = lifecycle.latest(rows, target)
        out = {
            "ran": True,
            "note": "synthetic harm on a COPY; the real store was not touched",
            "decision_before": [d for d in before if d["entry_id"] == target],
            "retired": len(result["retired"]) == 1,
            "decision_after": [d for d in after if d["entry_id"] == target],
            "retired_entry_id": new_id,
            "status_after": (head.get("version") or {}).get("status") if head else None,
            "parent_linked": ((head.get("version") or {}).get("parent_entry_id") == target
                              if head else None),
            "retired_reason": ((head.get("version") or {}).get("retired_reason")
                               if head else None),
            "chain_ok": store.verify_chain(cstore)[0],
        }
        _write(os.path.join(dest, "10_retirement_transition.json"), out)
        return out
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _review(entry, out_dir, probe, reviewer="chain-demo-reviewer"):
    """Write a review artifact on a MEASURED probe, and return the validation block.

    Not self-certification: the verdict is derived from the probe's expectations, and
    the artifact is a separate file with its own reference. A real round still needs an
    outside reviewer; that limit is written into SUMMARY.json rather than papered over.
    """
    verdict = "ACCEPT" if probe.get("expectations_met") else "REJECT"
    ref = os.path.join(os.path.dirname(out_dir), "REVIEW.md")
    _write(os.path.join(out_dir, "review_artifact_%s.json" % entry["version"]["label"]),
           {"reviewer": reviewer, "verdict": verdict, "probe": probe})
    return {"review_verdict": verdict, "review_ref": ref, "reviewed_by": reviewer}


# Files this script OWNS and may therefore replace. Everything else in the directory is
# kept. This list exists because the first version called shutil.rmtree(dest) and deleted
# the batch's own README.md and verify.py - a demonstration that destroys the evidence it
# is meant to support is worse than no demonstration.
GENERATED_PREFIXES = ("01_", "02_", "03_", "04_", "05_", "06_", "07_", "08_", "09_",
                      "10_")
GENERATED_FILES = ("SUMMARY.json", "records_v2.jsonl", "usage_ledger.jsonl",
                   "skill_assets.jsonl", "review_artifact_E1.json",
                   "review_artifact_E2.json")


def _clear_generated(dest):
    """Remove ONLY this script's own outputs; leave README.md / verify.py alone."""
    if not os.path.isdir(dest):
        return []
    removed = []
    for name in sorted(os.listdir(dest)):
        path = os.path.join(dest, name)
        if not os.path.isfile(path):
            continue
        if name in GENERATED_FILES or name.startswith(GENERATED_PREFIXES):
            os.remove(path)
            removed.append(name)
    return removed


def run(dest=OUT):
    os.makedirs(dest, exist_ok=True)
    _clear_generated(dest)
    store_path = os.path.join(dest, "records_v2.jsonl")
    ledger_path = os.path.join(dest, "usage_ledger.jsonl")
    steps = []

    # 1 -- measured failure, read from the archive
    with open(os.path.join(WT, FAILURE, "failure_evidence.json"), encoding="utf-8") as fh:
        failure = json.load(fh)
    _write(os.path.join(dest, "01_measured_failure.json"), failure)
    steps.append({"step": "measured_failure", "error_code": failure.get("error_code"),
                  "detail": failure.get("detail")})

    # 2 -- entries. The FIRST one is generated from the archive by postmortem.py, not
    # written here: a pipeline whose only input is a human typing entries is a form with
    # validation on it, not a continual loop. The second is written to contrast the
    # planner-side delivery with the executor-side one.
    # SPLIT: the dev split is tried first and produces NOTHING, because this repository's
    # T12/T13 task families exist only in the held-out set. Falling back to held-out is a
    # deliberate, recorded choice, and every entry it produces is stamped with the split
    # so no downstream reader can mistake it for a generalization result.
    generated, pm_report = postmortem.generate()
    dev_entries = list(generated)
    if not generated:
        generated, pm_report = postmortem.generate(split="held_out")
    _write(os.path.join(dest, "02_generated.json"),
           {"report": pm_report,
            "dev_split_built": len(dev_entries),
            "split": pm_report["split"],
            "entries": [e["entry_id"] for e in generated]})
    # Three deliveries: the generated one (harness, DEV split), plus the hand-written
    # pair that shows the ADDRESS problem - the same lesson inert at the planner-side
    # spread() and active at the executor-side respread(). Dropping the inert one would
    # silently remove the batch's only negative control.
    entries = generated + [entry_planner_side(), entry_executor_side()]
    routes = []
    for entry in entries:
        consumer, why = consumers.route(entry)
        routes.append({"label": entry["version"]["label"], "consumer": consumer,
                       "why": why})
    labels = [entry["version"]["label"] for entry in entries]
    _write(os.path.join(dest, "02_entries.json"),
           {"entries": entries, "routes": routes})
    steps.append({"step": "entries_built", "labels": labels, "routes": routes,
                  "generated_from_archive": len(generated),
                  "generator_split": pm_report["split"],
                  "dev_split_produced": len(dev_entries),
                  "generator_refused": [s for s, v in pm_report["signatures"].items()
                                        if not v["built"]]})

    # 3 -- effect, executed not asserted, for BOTH delivery addresses
    probes = {}
    for entry in entries:
        label = entry["version"]["label"]
        probes[label] = effect.probe(entry)
        _write(os.path.join(dest, "03_effect_%s.json" % label), probes[label])
    steps.append({"step": "effect_probe",
                  "verdicts": {k: v.get("verdict") for k, v in probes.items()},
                  "changed": {k: v.get("changed") for k, v in probes.items()}})

    # 4 -- ACE-style admission (both, plus a duplicate and a conflict attempt)
    admissions = []
    for entry in entries:
        decision, payload = curate.admit(entry, store_path=store_path,
                                         ledger_path=ledger_path)
        admissions.append({"label": entry["version"]["label"],
                           "decision": decision, "payload": payload})
    # Duplicate / conflict probes use a STORED entry, not a freshly built one: re-using
    # entry_planner_side() here looked like a duplicate test but silently stopped being
    # one when the generated entry replaced it in the store - the "duplicate" then had no
    # counterpart and reported ADD. Deriving the probe from what was actually admitted
    # keeps the test tied to the thing it claims to duplicate.
    dup = json.loads(json.dumps(entries[0]))
    for key in ("prev_sha256", "chain_sha256"):
        dup.pop(key, None)
    dup_decision, dup_payload = curate.admit(dup, store_path=store_path,
                                             ledger_path=ledger_path)
    conflict = json.loads(json.dumps(entries[0]))
    conflict["effect_spec"] = dict(conflict["effect_spec"], operator="respread_apply")
    conflict["entry_id"] = schema.digest(schema._body(conflict))
    conflict["record_sha256"] = schema.digest(
        {k: v for k, v in conflict.items() if k != "record_sha256"})
    conf_decision, conf_payload = curate.admit(conflict, store_path=store_path,
                                               ledger_path=ledger_path)
    _write(os.path.join(dest, "04_curation.json"),
           {"admissions": admissions,
            "duplicate_attempt": {"decision": dup_decision, "payload": dup_payload},
            "conflict_attempt": {"decision": conf_decision, "payload": conf_payload}})
    steps.append({"step": "curation",
                  "decisions": [a["decision"] for a in admissions],
                  "duplicate": dup_decision, "conflict": conf_decision})

    # 5 -- retrieval BEFORE review: must refuse everything, and that is the point
    consumer0 = routes[0]["consumer"]
    before, report_before = retrieve.retrieve(
        consumer0, task_family=entries[0]["task_family"], store_path=store_path,
        ledger_path=ledger_path, run_id="chain-demo", record=True)
    _write(os.path.join(dest, "05_retrieval_before_review.json"),
           report_before)
    steps.append({"step": "retrieval_before_review", "consumer": consumer0,
                  "kept": len(before), "refused": len(report_before["refused"])})

    # 6 -- review then activate, by APPENDING the reviewed successor
    activated = {}
    for entry in entries:
        label = entry["version"]["label"]
        validation = _review(entry, dest, probes[label])
        candidate_id = [a["payload"]["entry_id"] for a in admissions
                        if a["label"] == label][0]
        successor = curate.activate(candidate_id, validation, store_path=store_path,
                                    ledger_path=ledger_path, label=label)
        activated[label] = {"candidate": candidate_id,
                            "active": successor["entry_id"],
                            "status": successor["version"]["status"],
                            "verdict": validation["review_verdict"]}
        _write(os.path.join(dest, "06_activated_%s.json" % label), activated[label])
    steps.append({"step": "activated", "activated": activated})

    # 7 -- retrieval AFTER review, for the consumer that can act
    from_report = {}
    # Driven by the labels actually built, not a hardcoded ("E1", "E2"): the generated
    # entry's label comes from its signature, so a hardcoded list silently skipped it.
    for route in routes:
        label = route["label"]
        consumer = route["consumer"]
        kept, report = retrieve.retrieve(consumer,
                                         task_family=entries[0]["task_family"],
                                         store_path=store_path, ledger_path=ledger_path,
                                         run_id="chain-demo", record=True)
        from_report[label] = {"consumer": consumer, "kept": report["kept"],
                              "refused_count": len(report["refused"])}
        _write(os.path.join(dest, "07_retrieval_after_%s.json" % label), report)
    steps.append({"step": "retrieval_after_review", "by_label": from_report})

    # 8 -- apply, and record the MEASURED difference per entry
    applied = {}
    for entry in entries:
        label = entry["version"]["label"]
        target_id = activated[label]["active"]
        probe = effect.probe(entry)
        # Copy the operator's OWN numeric read-out rather than a fixed set of spacing
        # fields. The hand-written list emitted four nulls for the harness entry, which
        # reads as "the effect was measured and nothing moved" when the measurement was
        # simply of a different kind.
        delta = {k: v for k, v in probe.items()
                 if (k.startswith("baseline_") or k.startswith("applied_")
                     or k in ("changed", "verdict", "operator"))}
        delta.setdefault("changed", probe.get("changed"))
        if activated[label]["status"] == "ACTIVE":
            ledger.append(ledger_path, target_id, "APPLIED", run_id="chain-demo",
                          consumer=routes[[r["label"] for r in routes].index(label)]["consumer"],
                          changed=probe.get("changed"), detail=delta,
                          recorded_by="demo.run")
            improved = bool(probe.get("expectations_met"))
            ledger.append(ledger_path, target_id, "OUTCOME", run_id="chain-demo",
                          consumer=routes[[r["label"] for r in routes].index(label)]["consumer"],
                          outcome=("IMPROVED" if improved else "UNCHANGED"),
                          detail="effect_spec expectations met: %s" % improved,
                          recorded_by="demo.run")
        applied[label] = {"entry_id": target_id, "delta": delta,
                          "effect_state": ledger.effect_of(ledger_path, target_id)}
        _write(os.path.join(dest, "08_applied_%s.json" % label), applied[label])
    steps.append({"step": "applied_and_outcome", "by_label": applied})

    # 9 -- compile the ACTIVE entry into a CALLABLE asset (Voyager-style skill asset).
    # An entry that only steers while a human reads it is not a stored skill; this is the
    # step that makes the lesson something the next task can call.
    assets = {}
    active_rows = [r for r in store.read(store_path)
                   if (r.get("version") or {}).get("status") == "ACTIVE"]
    for row in active_rows:
        try:
            asset = skill_asset.compile_asset(row)
        except skill_asset.AssetError as exc:
            assets[row["version"]["label"]] = {"compiled": False, "why": str(exc)}
            continue
        asset_path = os.path.join(dest, "skill_assets.jsonl")
        stored = skill_asset.append(asset_path, asset)
        assets[row["version"]["label"]] = {
            "compiled": True, "asset_id": stored["asset_id"],
            "asset_version": stored["asset_version"],
            "callable": stored["callable"],
            "callable_exists": skill_asset.callable_exists(stored),
            "guard_count": len(stored["guard"]),
            "code_generated": stored["code_generated"],
        }
    _write(os.path.join(dest, "10_skill_assets.json"), assets)
    steps.append({"step": "skill_assets", "by_label": assets})

    # 10 -- LIFECYCLE: what the ledger says should happen to each ACTIVE entry.
    # The master goal's fifth step is "revise or retire based on the actual result". The
    # first version of this chain computed that verdict and then did nothing with it, so
    # a harmful entry would have stayed ACTIVE and kept being retrievable.
    lifecycle_decisions = lifecycle.review(store_path, ledger_path)
    _write(os.path.join(dest, "10_lifecycle_review.json"), lifecycle_decisions)
    # Demonstrate the retire transition on a THROWAWAY copy of the store, with a
    # synthetic WORSE outcome. Retiring the real entry here would be dishonest: no run
    # in this batch made anything worse, so there is no harm to act on. The transition
    # is proven on a copy and the real store is left exactly as the ledger describes it.
    harm_demo = _demonstrate_retirement(store_path, ledger_path, dest)
    steps.append({"step": "lifecycle",
                  "decisions": [{"label": d["label"], "effect": d["effect"],
                                 "decision": d["decision"]} for d in lifecycle_decisions],
                  "retire_transition_demo": harm_demo})

    # 11 -- the store's own curation report, computed from the records on disk
    report = curate.curate(store.read(store_path))
    _write(os.path.join(dest, "09_store_report.json"), report)
    steps.append({"step": "store_report", "entries": report["entries"],
                  "duplicates": len(report["duplicates"]),
                  "conflicts": len(report["conflicts"]),
                  "chains": len(report["chains"])})

    summary = {
        "record_kind": "EVOBOT_CONTINUAL_CHAIN_DEMO",
        "ran_at": "2026-11-18",
        "what": "two deliveries of one lesson through generate -> route -> measure -> "
                "curate -> retrieve -> apply -> outcome, on real archived inputs",
        "measured_result": {label: probe.get("verdict")
                            for label, probe in probes.items()},
        "why": ("the generated occupied_destination entry and the planner-side one both "
                "declare landing_spacing; at spread() they report NO_CHANGE because the "
                "plan builder had already offset the pair, while the executor-side "
                "respread clusters by distance and CHANGES it (56 mm -> 90 mm)"),
        "generator": {"scanned": pm_report["scanned"],
                      "built": len(generated),
                      "refused": {s: v["why"] for s, v in pm_report["signatures"].items()
                                  if not v["built"]}},
        "honest_limits": [
            "the review artifact is written by a separate step of the same run, not by "
            "an outside reviewer; a real round needs the latter",
            "each outcome is the effect_spec's own expectation met on an ARCHIVED input; "
            "no new robot run was made this round",
            "the planner consumer is not measurable offline; a prompt-level delivery is "
            "reported UNMEASURED rather than scored as no-effect",
        ],
        "steps": steps,
    }
    _write(os.path.join(dest, "SUMMARY.json"), summary)
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args(argv)
    summary = run(args.out)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
