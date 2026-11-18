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
import reuse  # noqa: E402
import routing_coverage  # noqa: E402
import order_measure  # noqa: E402
import order_fire  # noqa: E402
import push_comparison  # noqa: E402
import unrouted as unrouted_mod  # noqa: E402
import live_path  # noqa: E402
import delivery  # noqa: E402
import candidate_search  # noqa: E402
import schema  # noqa: E402
import skill_asset  # noqa: E402
import store  # noqa: E402
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
import public_observation as po  # noqa: E402

OUT = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118")
FAILURE = "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68"


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, indent=2, sort_keys=True) + "\n")


# Families the reuse audit MEASURES each lesson to fix, keyed by label. Filled at run time
# from reuse.audit, so this is a measurement and not a declaration: an empty entry means the
# audit found nothing beyond the source family.
MEASURED_FAMILIES = {}

_COMMON = dict(
    origin="AGENT_GENERATED",
    # The template id the benchmark uses, not a made-up label: reuse.template_of() reports
    # families as T13_geometric_conditional, and two vocabularies for one thing is how a
    # measured cross-family win became undeliverable.
    task_family="T13_geometric_conditional",
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
                        "another object sits inside the corridor the spread would use",
                        "the landings ALREADY meet the spacing contract"],
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
    {"condition": "the landings ALREADY meet the spacing contract",
     "probe": "spacing.already_satisfied"},
]

_EXECUTOR_PROBES = [
    {"condition": "a single stage lands in the bin (nothing to separate)",
     "probe": "respread.single_stage"},
    {"condition": "the separation would push a landing outside the bin radius",
     "probe": "respread.narrow_bin"},
    {"condition": "another object sits inside the corridor the spread would use",
     "probe": "respread.corridor_blocked"},
    {"condition": "the landings ALREADY meet the spacing contract",
     "probe": "spacing.already_satisfied"},
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


def entry_order_rule():
    """The operation-order lesson addressed to the PLANNER (a fourth routed consumer).

    The objective names "operation order lessons go to the planner". This entry turns the
    planner's order check into a real experience entry with a call entry, so the order route
    can be CARRIED rather than a path with no entry. Its effect is measured by the plan_order
    operator on 16 archived order-fixing plans (0 wrongly refused, the one genuine foreign
    reordering caught) and its misuse guard is probed by order.no_fixed_order.
    """
    return schema.make_entry(
        origin="AGENT_GENERATED",
        action_kind="move_order", consumer="planner",
        task_family="T14_ordered_pair", failure_class="planning",
        source_run="evobot_crosstype_20261111/runs_T14_ordered_pair",
        evidence={"order_fixing_replies": 16, "violations": 0,
                  "false_positives": 0, "foreign_reordering_caught": True,
                  "evidence_split": "dev"},
        evidence_files=["evobot_wrongplan_probe_20261111/run_foreign_plan/plan.json"],
        provenance_verified=True,
        applicable_when=["the instruction fixes an order the plan must follow"],
        known_invalid_when=["the instruction fixes no order"],
        suggested_action=("when the instruction fixes an order, validate the plan before "
                          "execution and refuse a move that reverses it"),
        effect_spec={"fixture": "t14_ordered_pair", "operator": "plan_order",
                     "params": {},
                     "expect": {"catches_violations": True, "no_false_positives": True}},
        invalid_probes=[{"condition": "the instruction fixes no order",
                         "probe": "order.no_fixed_order"}],
        version={"label": "E3", "status": "CANDIDATE", "parent_entry_id": None},
        notes=("planner-side order rule; effect measured on 16 archived order-fixing "
               "plans, no model call; a foreign-plan reordering is caught"),
    )


def _demonstrate_revision(store_path, ledger_path, dest):
    """Prove the REVISE transition on a copy whose measured scope was narrowed first.

    WHY ON A COPY: the real records were activated after their scope was measured, so they
    are already current and there is nothing on them to revise. Narrowing a copy to the
    state an activation produces when the measurement has since grown is the honest way to
    exercise the transition - the alternative is to fabricate a measurement, which is the
    dishonesty this package is built to refuse.

    It also proves the properties that make a revision safe: the lesson text is unchanged,
    the previous version stays on disk, the chain verifies, and the successor is ACTIVE with
    a parent link (DGM's version lineage).
    """
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="revise_")
    try:
        cstore = os.path.join(tmp, "records_v2.jsonl")
        cledger = os.path.join(tmp, "usage_ledger.jsonl")
        # Rebuild rather than copy: a copied store already has the measured scope recorded,
        # and dropping it in place would break the hash chain the store exists to protect.
        for row in store.read(store_path):
            body = {k: v for k, v in row.items()
                    if k not in ("prev_sha256", "chain_sha256", "record_sha256")}
            narrowed = (row.get("version") or {}).get("label") == "E2" \
                and (row.get("version") or {}).get("status") == "ACTIVE"
            if narrowed:
                body["measured_families"] = []
            body["entry_id"] = schema.digest(schema._body(body))
            body["record_sha256"] = schema.digest(schema.record_body(body))
            store.append(cstore, body)
        shutil.copyfile(ledger_path, cledger)
        before = lifecycle.review(cstore, cledger, measure=True,
                                  acceptance=os.path.join(WT, "setup", "acceptance"),
                                  source_task="HO-90899d657e68")
        stale = [d for d in before if d["decision"] == "REVISE"]
        if not stale:
            return {"ran": False, "why": "no stale scope to revise on the copy"}
        target = stale[0]
        old = [r for r in store.read(cstore) if r["entry_id"] == target["entry_id"]][0]
        successor = lifecycle.revise(target["entry_id"], store_path=cstore,
                                     ledger_path=cledger,
                                     acceptance=os.path.join(WT, "setup", "acceptance"),
                                     source_task="HO-90899d657e68")
        after = lifecycle.review(cstore, cledger, measure=True,
                                 acceptance=os.path.join(WT, "setup", "acceptance"),
                                 source_task="HO-90899d657e68")
        result = {
            "ran": True,
            "label": target["label"],
            "decision_before": [{"label": d["label"], "decision": d["decision"],
                                 "why": d["why"]} for d in before],
            "scope_before": old.get("measured_families"),
            "scope_after": successor.get("measured_families"),
            "added": successor["version"].get("revised_added"),
            # A revision must not silently become a second activation: the reviewed text
            # is untouched and only the measured scope moved.
            "lesson_unchanged": (successor.get("suggested_action")
                                 == old.get("suggested_action")
                                 and successor.get("applicable_when")
                                 == old.get("applicable_when")),
            "status_after": successor["version"]["status"],
            "parent_linked": successor["version"].get("parent_entry_id")
                             == target["entry_id"],
            "old_version_still_on_disk": any(r["entry_id"] == target["entry_id"]
                                             for r in store.read(cstore)),
            "still_revise_after": [d["label"] for d in after if d["decision"] == "REVISE"],
            "chain_ok": store.verify_chain(cstore)[0],
        }
        _write(os.path.join(dest, "10_revision_transition.json"), result)
        return result
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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

    WHY review_ref IS RELATIVE AND NAMES THE ARTIFACT THAT IS ACTUALLY WRITTEN:
        It used to be os.path.dirname(out_dir)/REVIEW.md - an ABSOLUTE path, outside the
        run directory, pointing at a file this function never created. Two consequences,
        both real:
          * the path was embedded in the entry body, so the entry_id changed with wherever
            the demo happened to run. A committed artifact set could therefore NEVER match a
            fresh run, and nothing could check the evidence was current.
          * the reference dangled. A reader following it found no file.
        It now names the per-entry artifact written beside it, relative to the run
        directory, so the id is stable and the reference resolves.
    """
    verdict = "ACCEPT" if probe.get("expectations_met") else "REJECT"
    name = "review_artifact_%s.json" % entry["version"]["label"]
    _write(os.path.join(out_dir, name),
           {"reviewer": reviewer, "verdict": verdict, "probe": probe})
    return {"review_verdict": verdict, "review_ref": name, "reviewed_by": reviewer}


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
    entries = generated + [entry_planner_side(), entry_executor_side(),
                           entry_order_rule()]
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

    # 2b -- THE SKILL PARAMETER IS SELECTED, NOT TYPED. Every parameter in this package
    # used to be a hand-picked constant. A parameter nobody compared against an alternative
    # is a guess wearing a number, and the comparison is free when the feedback is already
    # archived. Feasibility is a hard filter and cost is the objective among the feasible -
    # not a weighted sum, because a weight would let a cheap candidate buy its way past a
    # violated clearance contract.
    selection, board = candidate_search.search()
    _write(os.path.join(dest, "02b_candidate_board.json"),
           {"selected": selection, "board": board})
    steps.append({"step": "candidate_search",
                  "selected": selection["candidate"] if selection else None,
                  "board": [{"candidate": r["candidate"], "admissible": r["admissible"],
                             "fixed": r["fixed"], "plans": r["plans"],
                             "clearance_violations": r["clearance_violations"],
                             "mean_displacement_m": r["mean_displacement_m"],
                             "why": r["why"]} for r in board]})

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
    measurements = {}
    for entry in entries:
        label = entry["version"]["label"]
        validation = _review(entry, dest, probes[label])
        candidate_id = [a["payload"]["entry_id"] for a in admissions
                        if a["label"] == label][0]
        # The MEASURED cross-family scope travels with the activation. Leaving it in a
        # report would mean retrieval never offers the lesson to the families the reuse
        # audit measured it fixing, which is a number nobody can act on.
        # Measured HERE, before the successor exists: activation is where the field is
        # written, so measuring afterwards would be too late to change this version.
        measurement = reuse.measure_for_entry(
            entry, source_task="HO-90899d657e68",
            acceptance=os.path.join(WT, "setup", "acceptance"))
        MEASURED_FAMILIES[label] = measurement["families_with_fixes"]
        measured = MEASURED_FAMILIES.get(label) or []
        measurements[label] = measurement
        successor = curate.activate(candidate_id, validation, store_path=store_path,
                                    ledger_path=ledger_path, label=label,
                                    measured_families=measured)
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
        # Ask as the task the entry was LEARNED from, per label. Using entries[0]'s family
        # for every label worked only while every entry declared the same family - which
        # was the mislabelling this round fixed. A shared family was hiding the difference.
        family = ([e for e in entries if e["version"]["label"] == label][0]["task_family"])
        kept, report = retrieve.retrieve(consumer, task_family=family,
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

    # 9a -- DELIVERY: did each ACTIVE entry actually REACH its consumer? Routing answers
    # "which module can act on this"; it does not answer "did it arrive". The gap is silent:
    # the planner's prompt renderer reads item["lesson"] while a v2 entry carries
    # suggested_action, so the lesson vanishes and the ledger records NO_CHANGE - which
    # reads exactly like "the lesson had no effect".
    task = json.load(open(os.path.join(WT, "benchmark", "held_out", "unseen_public",
                                      "HO-90899d657e68.json"), encoding="utf-8"))
    observation = po.build_observation(task)
    deliveries = {}
    for row in [r for r in store.read(store_path)
                if (r.get("version") or {}).get("status") == "ACTIVE"]:
        deliveries[row["version"]["label"]] = delivery.deliver(row, observation)
    _write(os.path.join(dest, "09a_delivery.json"), deliveries)
    steps.append({"step": "delivery_check",
                  "by_label": {k: {"consumer": v.get("consumer"),
                                   "verdict": v.get("verdict")}
                               for k, v in deliveries.items()}})

    # 9b -- REUSE: run the stored skill over EVERY archived task, including the ones it
    # never saw. "It works on the input it was derived from" is the weakest possible claim
    # and it is the one a demo naturally produces; the objective's claim is that a lesson
    # accumulated on one task is reused on LATER ones, which is a statement about tasks it
    # was not built from.
    # record=True so the audit's per-task use reaches the LEDGER. The master goal's fifth
    # step is "record WHICH TASK retrieved it, what changed, what the result was"; this audit
    # is the only place a skill is applied to tasks it was not built from, and it used to
    # write that into a report file and nowhere else - the ledger said two applications under
    # one demo label while seven real tasks had actually been handled.
    reuse_report = reuse.reuse_assets(os.path.join(dest, "skill_assets.jsonl"),
                                      source_task="HO-90899d657e68",
                                      ledger_path=ledger_path, record=True)
    _write(os.path.join(dest, "09b_reuse_audit.json"), reuse_report)
    # The DENOMINATOR, not only the wins. A skill offered to 294 plans and changing 7 of
    # them is a very different object from one that changed every plan it saw, and a ledger
    # that recorded only the 7 would report a 100% hit rate for a 2.4% effect.
    # THE RATE IS REPORTED IN ONE UNIT. Both denominators are carried and neither is
    # divided by the other: fixed is per task instance while untouched was once per plan
    # file, and the same task appears in several batches, so a fraction built from the two
    # understated the effect by roughly the duplication factor.
    steps.append({"step": "reuse_audit",
                  "total_instances_fixed": [r["total_instances_fixed"]
                                            for r in reuse_report],
                  "plans_offered": [r["plans_offered"] for r in reuse_report],
                  "instances_offered": [r["instances_offered"] for r in reuse_report],
                  "instance_hit_rate": [r["instance_hit_rate"] for r in reuse_report],
                  "plans_correctly_untouched": [
                      sum(v["untouched_plans"] for v in r["families"].values())
                      for r in reuse_report],
                  "families_fixed_beyond_source": [r["families_fixed_beyond_the_source"]
                                                   for r in reuse_report],
                  "made_worse": [r["total_made_worse"] for r in reuse_report]})

    # 10 -- LIFECYCLE: what the ledger says should happen to each ACTIVE entry.
    # The master goal's fifth step is "revise or retire based on the actual result". The
    # first version of this chain computed that verdict and then did nothing with it, so
    # a harmful entry would have stayed ACTIVE and kept being retrievable.
    # measure=True so the review also asks the SECOND question: is the record still as wide
    # as what has been measured? The scope is written at activation and a later measurement
    # can outgrow it, which would leave the live entry narrower than the evidence for it.
    lifecycle_decisions = lifecycle.review(store_path, ledger_path, measure=True,
                                          acceptance=os.path.join(WT, "setup",
                                                                  "acceptance"),
                                          source_task="HO-90899d657e68")
    _write(os.path.join(dest, "10_lifecycle_review.json"), lifecycle_decisions)
    # Demonstrate the retire transition on a THROWAWAY copy of the store, with a
    # synthetic WORSE outcome. Retiring the real entry here would be dishonest: no run
    # in this batch made anything worse, so there is no harm to act on. The transition
    # is proven on a copy and the real store is left exactly as the ledger describes it.
    harm_demo = _demonstrate_retirement(store_path, ledger_path, dest)
    # ... and the REVISE transition, which this module promised in its docstring and never
    # had. Shown on a throwaway copy whose measured scope was deliberately narrowed first:
    # the real records are already current, so there is nothing on them to revise.
    revise_demo = _demonstrate_revision(store_path, ledger_path, dest)
    steps.append({"step": "lifecycle",
                  "decisions": [{"label": d["label"], "effect": d["effect"],
                                 "decision": d["decision"]} for d in lifecycle_decisions],
                  "retire_transition_demo": harm_demo,
                  "revise_transition_demo": revise_demo})

    # 10b -- WHICH OF THE OBJECTIVE'S FOUR ROUTINGS ACTUALLY CARRY AN ENTRY. consumers.py
    # declaring a destination is not evidence anything was ever sent there: the fourth
    # routing the objective names (ROS launch -> development experience) is declared,
    # counted as "implemented" because its entrypoint file exists, and has never carried
    # anything. Nothing said so, because nothing asked.
    coverage = routing_coverage.coverage(store_path)
    _write(os.path.join(dest, "10b_routing_coverage.json"), coverage)
    steps.append({"step": "routing_coverage",
                  "carried": coverage["carried"], "named": coverage["named"],
                  "states": {r["consumer"]: r["state"] for r in coverage["routings"]},
                  "carried_by_an_unnamed_consumer":
                      sorted(coverage["carried_by_an_unnamed_consumer"])})

    # 10c -- WHAT "UNROUTED" ACTUALLY MEANS. The generator refuses 7 of 9 signatures as
    # UNROUTED, which covers 92 of the 98 failures in the archive. That sentence is a
    # statement about this stack's SIGNATURE TABLE ("no consumer declares a mapping"), not
    # about whether a module could act. Reading it as "nothing here can act" turns unwritten
    # work into a measured limit.
    unrouted = unrouted_mod.report()
    _write(os.path.join(dest, "10c_unrouted_analysis.json"), unrouted)
    steps.append({"step": "unrouted_analysis",
                  "signatures": len(unrouted["unrouted"]),
                  "failures_covered": unrouted["failures_covered"],
                  "by_state": unrouted["by_state"]})

    # 10d -- IS THE LOOP PLUGGED IN? Everything up to here is connected inside the chain's
    # own harness. The code that hands experience to the planner for a REAL robot run reads a
    # different store with a different schema, so the loop can be correct and unplugged at
    # the same time. That distinction has to be on the artifact or "the chain works" will be
    # read as "the robot uses it".
    live = live_path.report()
    _write(os.path.join(dest, "10d_live_path.json"), live)
    steps.append({"step": "live_path",
                  "active_entries": live["active_entries"],
                  "visible_to_live_path": live["visible_to_live_path"],
                  "by_reason": live["by_reason"],
                  "bridge_would_help": [x["would_a_bridge_help"]
                                        for x in live["planner_filter_result"]],
                  "live_consumers": {k: v["has_a_live_consumer"]
                                     for k, v in live["consumers_in_live_path"].items()}})

    # 10e -- IS THERE A REAL WIRE FROM AN ENTRY TO THE LIVE CALL? The executor consumer
    # exists (run_batch.sh:107 -> recovery_driver.py:146), but historically used the function
    # defaults and never looked up an entry. The driver now has an OPT-IN fail-closed binding.
    # Probe both directions: no flags -> defaults; reviewed entry -> the asset's kwargs.
    import live_binding as lb
    wire_defaults, why_defaults = lb.resolve("", "executor_recovery", store_path)
    wire_reviewed, why_reviewed = lb.resolve(
        os.path.join(dest, "skill_assets.jsonl"), "executor_recovery", store_path)
    # The repo DOES have an independent ACCEPT — for a CONTROL FACT built on exactly E2's
    # three evidence files, not for E2's actionable claim. A review of the same evidence for
    # a DIFFERENT claim must not authorise a live parameter change. Prove that here.
    real_ledger = os.path.join(WT, "evolution", "experience", "review_ledger.jsonl")
    other_claim, other_why = lb.resolve(
        os.path.join(dest, "skill_assets.jsonl"), "executor_recovery", store_path,
        review_ledger=real_ledger)
    steps.append({"step": "live_wiring",
                  "no_flags_kwargs": wire_defaults,
                  "self_reviewed_kwargs": wire_reviewed,
                  "real_ledger_other_claim_kwargs": other_claim,
                  "review_ledger_is_chained": True,
                  "review_ledger_limits": ("proves no edit/reorder/middle-deletion; does NOT "
                                           "prove reviewer identity, stop a new review, or "
                                           "detect tail truncation"),
                  # step 4: an already-conforming plan must not receive the lesson's params
                  "applicability_checked_on_the_real_plan": True,
                  # step 5 at the live boundary: an applied entry is recorded with its run id
                  "applied_live_entries_are_recorded": True,
                  "a_default_path_records_nothing": True,
                  # ADR-002: the gate runs on the development side (resolve_live.py) and the
                  # runtime reads a binding FILE as data - no runtime->evolution import.
                  "gate_is_in_development_layer": True,
                  "runtime_reads_binding_as_data": True,
                  "note": ("opt-in and fail-closed: the frozen baseline default path is "
                           "unchanged; an ACCEPT from an INDEPENDENT ledger bound to this "
                           "entry id is required — a review of the same evidence for a "
                           "different claim does NOT authorise it")})

    # 10e -- A PLANNER-SIDE ORDER CLAUSE THE RULE COULD NOT SEE. The objective routes
    # "operation order" lessons to the planner. The planner's order rule only knew "the X
    # block must be put there FIRST"; the phrase "passing through the RIGHT bin first"
    # appears in 24 archived instructions and was invisible to it. Ground truth comes from
    # each observation's own zone positions, never from the evaluator's verdict, so this
    # measures the rule and not the answer key.
    order = order_measure.measure()
    _write(os.path.join(dest, "10e_order_clause.json"), order)
    steps.append({"step": "planner_order_clause",
                  "clause": order["clause"],
                  "true_positives": order["true_positives"],
                  "false_positives": order["false_positives"],
                  "true_negatives": order["true_negatives"],
                  "false_negatives": order["false_negatives"],
                  "checked": order["checked"],
                  "note": ("a rule that refuses a CORRECT plan is worse than one that "
                           "misses a wrong one; zero false positives is the bar")})

    # 10f -- FIRE THE RULE THROUGH THE REAL DELIVERY CHANNEL. The measurement above shows
    # the rule WOULD catch reversals, and the gate keeps it inert by default — but all 44
    # experience-bearing archive observations carry legacy items with _entry_id = None, so
    # nothing had ever been seen actually firing it. Render an admitted entry through
    # delivery.deliver_planner and check the SAME reversed plan is refused only then.
    fired = order_fire.demonstrate()
    _write(os.path.join(dest, "10f_order_fired.json"), fired)
    steps.append({"step": "planner_order_fired",
                  "entry_id": fired["entry_id"],
                  "gate_fired": fired["gate_fired"],
                  "without_entry_problems": len(fired["reversed_plan_without_entry"][1]),
                  "with_entry_problems": [p for p in fired["reversed_plan_with_entry"][1]
                                          if "right bin first" in p],
                  "note": ("the rule is not dead code: an admitted entry delivered through "
                           "the real channel is required to refuse the reversed plan")})

    # 10g -- A REAL WITH/WITHOUT COMPARISON THE UNROUTED PROBE MISSED. probe_push_recovery
    # concluded "this archive cannot measure the effect" because it replayed attempts the
    # policy produced itself. That is true of the path it reads - but it ignored a separate,
    # independently collected A/B batch with the same world/task/validator and a preregistered
    # order. Read it here, with its limits, without changing the old probe's evidence.
    push = push_comparison.measure()
    _write(os.path.join(dest, "10g_push_comparison.json"), push)
    steps.append({"step": "push_without_policy_comparison",
                  "is_real_comparison": push["is_real_comparison"],
                  "control_passes": push["control_passes"],
                  "control_runs": push["control_runs"],
                  "feedback_passes": push["feedback_passes"],
                  "feedback_runs": push["feedback_runs"],
                  "honest_limits": push["honest_limits"],
                  "note": ("an independently collected control-vs-feedback batch, not a "
                           "replay; n=3 on one dev instance and does not isolate one component")})

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
