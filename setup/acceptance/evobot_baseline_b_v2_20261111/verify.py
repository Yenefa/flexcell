#!/usr/bin/env python3
"""Verifier for the Baseline B v2 PLANNING batch.

WHAT THIS VERIFIES, AND WHAT IT DELIBERATELY DOES NOT

It verifies that the planning half did what the README says: every recorded plan
is contract-valid, every observation was free of the answer, the credential came
from the budget gate, and the plan-level check agrees with the archived numbers.

It does NOT verify task success. No robot moved. There is no final state, so there
is no evaluator verdict and this batch must not be labelled Simulation Tested or
above. The rung it declares is "Unit Tested + plan-level", and that is the truth.

EVERY CHECK BELOW CAN FAIL. verify_baseline_b.py proves the library-level ones by
mutation; this file re-derives the batch-level numbers from the artefacts so a
hand-edited README cannot pass.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "baselines"))
sys.path.insert(0, str(ROOT / "runtime" / "planner"))

import check_plans as cp
import public_observation as po

PLANS = HERE / "plans"


def fail(message):
    print("FAIL: " + message)
    return 1


def main():
    problems = []

    # (1) the artefacts the README cites must exist and agree with it
    for required in ("plan_level_check.json", "mutation_proof.json",
                     "transient_retry.json", "tests.txt"):
        if not (HERE / required).exists():
            problems.append("missing artefact: " + required)
    if problems:
        return fail("; ".join(problems))

    recorded = json.loads((HERE / "plan_level_check.json").read_text(encoding="utf-8"))

    # (2) re-derive the numbers from the plan directories, not from the summary
    dirs = sorted(d for d in PLANS.iterdir() if d.is_dir())
    if not dirs:
        return fail("no plan directories; the batch would be vacuous")
    rows = [cp.check_one(str(d), d.name) for d in dirs]
    planned = [r for r in rows if r.get("planned")]
    correct = [r for r in planned if r.get("plan_level_correct")]

    if recorded["instances"] != len(rows):
        problems.append("README says %d instances, disk has %d"
                        % (recorded["instances"], len(rows)))
    if recorded["planned"] != len(planned):
        problems.append("README says %d planned, disk says %d"
                        % (recorded["planned"], len(planned)))
    if recorded["plan_level_correct"] != len(correct):
        problems.append("README says %d plan-level correct, disk says %d"
                        % (recorded["plan_level_correct"], len(correct)))
    if len(planned) != len(correct):
        problems.append("%d planned but only %d plan-level correct: %s"
                        % (len(planned), len(correct),
                           [r["task_id"] for r in planned if not r.get("plan_level_correct")]))

    # (3) every observation handed to the agent must be answer-free
    for d in dirs:
        obs_path = d / "observation_input.json"
        if not obs_path.exists():
            problems.append("%s: no observation recorded" % d.name)
            continue
        obs = json.loads(obs_path.read_text(encoding="utf-8"))
        blob = json.dumps(obs).lower()
        for leak in ("expected", "placement", "evaluator", "tolerance",
                     "template", "random_seed", "unmoved"):
            if leak in blob:
                problems.append("%s: observation leaks %r" % (d.name, leak))
        for line in json.dumps(obs, indent=1).splitlines():
            if "target_box_" in line and "zone_" in line:
                problems.append("%s: observation pairs an object with a bin: %s"
                                % (d.name, line.strip()))
                break

    # (4) every credential must have come from the gate
    for d in dirs:
        reply_path = d / "agent_reply.json"
        if not reply_path.exists():
            problems.append("%s: no agent reply recorded" % d.name)
            continue
        reply = json.loads(reply_path.read_text(encoding="utf-8"))
        if reply.get("key_source") != "evobot_llm_key.sh":
            problems.append("%s: credential did not come from the budget gate (%r)"
                            % (d.name, reply.get("key_source")))
        if "evobot_llm_key.sh" not in str(reply.get("gate", "")):
            problems.append("%s: no gate path recorded" % d.name)
        if not reply.get("key_fingerprint"):
            problems.append("%s: no key fingerprint; provenance unrecorded" % d.name)

    # (5) every emitted plan must satisfy the RunComposite contract
    for d in dirs:
        plan_path = d / "plan.json"
        if not plan_path.exists():
            continue  # a rejected plan legitimately has none; counted in (2)
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        required = {"task_id", "initial_objects", "stages", "final_empty_positions",
                    "position_tolerance_m", "clearance_m", "motion_profile_id"}
        if set(plan) != required:
            problems.append("%s: plan fields %s" % (d.name, sorted(set(plan) ^ required)))
            continue
        if not 1 <= len(plan["stages"]) <= 8:
            problems.append("%s: %d stages" % (d.name, len(plan["stages"])))
        ids = [s["stage_id"] for s in plan["stages"]]
        if len(set(ids)) != len(ids):
            problems.append("%s: duplicate stage ids" % d.name)
        if not 0.05 <= plan["clearance_m"] <= 0.25:
            problems.append("%s: clearance %s outside 0.05..0.25"
                            % (d.name, plan["clearance_m"]))
        if not 0 < plan["position_tolerance_m"] <= 0.06:
            problems.append("%s: tolerance %s outside contract"
                            % (d.name, plan["position_tolerance_m"]))

    # (5b) every stage destination must land inside a bin the TASK declared.
    #
    # FOUND BY THE LEAD (2026-11-11): the checks above only validate a plan's STRUCTURE --
    # field names, stage count, unique ids, clearance and tolerance ranges. Set a stage
    # destination to [9.9, 9.9, 9.9] and every one of them still passes, because 9.9 m from the
    # table is not structurally invalid. The verifier then reports PLAN_LEVEL_VERIFIED on a plan
    # that could never execute. Structure is not intent: a destination has to be somewhere the
    # task actually offered. This is checked against the observation the agent was given, not
    # against the answer, so it stays a public-information check.
    for d in dirs:
        plan_path = d / "plan.json"
        obs_path = d / "observation_input.json"
        if not (plan_path.exists() and obs_path.exists()):
            continue
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        obs = json.loads(obs_path.read_text(encoding="utf-8"))
        zones = obs.get("zones") or []
        if isinstance(zones, dict):
            zones = [dict(v, name=k) for k, v in zones.items()]
        centres = []
        for z in zones:
            pose = z.get("position") or z.get("pose")
            if pose:
                centres.append((z.get("name"), [float(x) for x in pose[:2]]))
        if not centres:
            problems.append("%s: observation declares no zones to check against" % d.name)
            continue
        for s in plan.get("stages", []):
            dest = s.get("destination") or s.get("place_pose")
            if not dest:
                continue
            near = [n for n, c in centres
                    if abs(float(dest[0]) - c[0]) <= 0.06 and abs(float(dest[1]) - c[1]) <= 0.06]
            if not near:
                problems.append(
                    "%s: stage %s targets %s, which is not within any declared bin %s"
                    % (d.name, s.get("stage_id"), [round(float(x), 3) for x in dest[:2]],
                       [n for n, _ in centres]))

    # (6) the mutation proof must still say every check can fail
    mutation = json.loads((HERE / "mutation_proof.json").read_text(encoding="utf-8"))
    if not mutation.get("every_check_is_proven_to_be_able_to_fail"):
        problems.append("mutation proof does not show all checks can fail")
    if not mutation.get("control_passes_on_unmutated_code"):
        problems.append("control run failed: the probes are not measuring the property")
    if not mutation.get("tracked_files_unmodified"):
        problems.append("a mutation leaked into the tracked sources")

    # (7) the transient failure must be preserved, not deleted
    if not (HERE / "failed_run_preserved" / "agent_reply.json").exists():
        problems.append("the one failed run was not preserved as evidence")

    if problems:
        for p in problems:
            print("FAIL: " + p)
        return 1

    print(json.dumps({
        "verdict": "EVOBOT_BASELINE_B_V2_PLANNING_VERIFIED",
        "rung": "Unit Tested + plan-level analysis (NO robot run, NOT Simulation Tested)",
        "instances": len(rows),
        "planned": len(planned),
        "plan_level_correct": len(correct),
        "templates": sorted({r["template"] for r in rows if r.get("template")}),
        "not_planned": [r["task_id"] for r in rows if not r.get("planned")],
        "total_tokens": sum(r.get("tokens") or 0 for r in rows),
        "observations_answer_free": True,
        "all_credentials_from_gate": True,
        "all_plans_contract_valid": True,
        "mutation_proof_intact": True,
        "failed_run_preserved": True,
        "false_success": None,
        "false_success_note": ("NOT MEASURED. false_success needs a world state and an "
                               "agent claim; nothing executed, so reporting 0 here "
                               "would be a vacuous zero - the exact mistake "
                               "evobot_honesty_retraction_20261111 was written about."),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
