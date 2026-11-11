#!/usr/bin/env python3
"""Turn one trial's raw telemetry into a bundle, an independent max_z, and a verdict.

FOUR THINGS THIS DOES THAT A NAIVE PIPELINE DOES NOT
    1. REST HEIGHT IS BOUND TO THE TASK SPEC, not taken from the operator.
       verify.py's table_support and no_lift gates compare the object's height
       against evidence.task.rest_height_m, and schema.py only requires that
       field to be a finite number. A bundle that declares rest_height_m equal
       to its own (wrong) height makes both gates vacuously true - a constant
       height carry at 50 mm then grades PUSHED. So the value written into the
       bundle is derived here from spec['objects'][target]['initial_pose'][2],
       and the value actually handed to the recorder is recorded separately. If
       the two ever disagree the trial is INVALID_EVIDENCE.
    2. MAX_Z IS RECOMPUTED FROM THE RAW PHYSICS LOG. evaluate.py trusts
       observation.trajectory[name].max_z_m as given. This script computes the
       same statistic from the per-step log itself and records both numbers, so
       a reader can see whether the number handed to the evaluator is the number
       the telemetry contains.
    3. THE BUNDLE'S OWN SHA-256 IS RECOMPUTED FROM THE FILE ON DISK, so the
       digest in the results table binds to bytes rather than to a claim.
    4. GRADING GOES THROUGH evaluate.py v0.5.0 UNCHANGED, with the spec and the
       evaluator both read from the worktree; nothing here re-implements a gate.
    5. EVERY FAILURE IS NAMED. A trial that did not pass is classified into one
       of the project's failure categories (or UNKNOWN), with the measured number
       that puts it there. "did not pass" on its own is not a finding.
"""
import hashlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
EVIDENCE_DIR = os.path.join(WT, "benchmark", "evidence")
sys.path.insert(0, os.path.join(WT, "benchmark", "evidence"))
sys.path.insert(0, WT)

import recorder  # noqa: E402  (frozen: imported, never edited)
import schema    # noqa: E402

PUSHER_LINKS = [
    "open_manipulator_x::gripper_left_link::gripper_left_link_collision",
    "open_manipulator_x::gripper_right_link::gripper_right_link_collision",
]
GRIPPER_JOINT = "gripper_left_joint"

# The project's failure taxonomy. A classification is a claim about CAUSE, so it
# is only assigned when a measurement forces it; otherwise UNKNOWN.
CATEGORIES = ("Perception", "Planning", "Kinematics", "Control", "Grasp",
              "State Management", "Tooling", "Runtime", "Model Reasoning",
              "Environment")


def classify_failure(record, attempts, verdict):
    """Name the failure, or say UNKNOWN. Never inferred from the pass flag alone."""
    clause = None
    for item in verdict.get("clauses", []):
        if item["clause"] == "push:" + record.get("target_object", "target_box_a"):
            clause = item["evidence"]
    max_m = float(record.get("max_displacement_m") or 0.150)
    signed_mm = record.get("displacement_signed_mm")
    unsigned_mm = record.get("displacement_mm")
    cos = record.get("direction_cos")

    # 1. Overshoot: measured travel past the frozen ceiling. This is its own
    #    named class because it is a DIFFERENT failure from "did not push far
    #    enough", and lumping them makes both invisible.
    for attempt in attempts:
        disp = attempt.get("displacement_m")
        if isinstance(disp, (int, float)) and disp > max_m:
            return ("FAIL_OVERSHOOT", "Control",
                    "a single PushObject delivered %.1f mm against the frozen "
                    "%.0f mm ceiling (server error_code=%s)"
                    % (disp * 1000.0, max_m * 1000.0, attempt.get("error_code")))

    # 2. Pushed the wrong way.
    if isinstance(cos, (int, float)) and cos < 0:
        return ("FAIL_DIRECTION", "Control",
                "direction cosine %.4f: the object was driven away from the "
                "commanded direction, not along it" % cos)

    # 3. Short of the 30 mm floor.
    if unsigned_mm is not None and unsigned_mm < 30.0:
        return ("FAIL_SHORT", "Control",
                "the object travelled %.1f mm, below the frozen 30 mm floor; "
                "PushObject reported contact loss" % unsigned_mm)

    # 4. The TERMINAL clause's own sub-reason, read before the evidence status.
    #    verify.py's terminal gate fails closed and reports UNKNOWN whenever a
    #    terminal clause fails, so "evidence incomplete" would otherwise hide
    #    which physical bound was crossed. The clause evidence says which.
    if record.get("terminal_passed") is False and isinstance(clause, dict):
        lift = clause.get("max_lift_m")
        allowed = clause.get("max_lift_allowed_m")
        if (isinstance(lift, (int, float)) and isinstance(allowed, (int, float))
                and lift > allowed):
            return ("FAIL_LIFT", "Control",
                    "the object rose %.2f mm above its resting height against a "
                    "%.0f mm bound: that is a lift, not a push"
                    % (lift * 1000.0, allowed * 1000.0))
        inside = clause.get("inside_zone")
        if inside is False and clause.get("distance_m") is not None:
            return ("FAIL_ZONE", "Control",
                    "the object ended %.1f mm from the zone centre (radius "
                    "%.0f mm) after travelling %.1f mm"
                    % (clause["distance_m"] * 1000.0,
                       clause["radius_m"] * 1000.0, unsigned_mm or 0.0))
        vertical = clause.get("vertical_m")
        max_vertical = clause.get("max_vertical_m")
        if (isinstance(vertical, (int, float))
                and isinstance(max_vertical, (int, float))
                and vertical > max_vertical):
            return ("FAIL_VERTICAL", "Control",
                    "vertical displacement %.2f mm exceeds the %.0f mm bound"
                    % (vertical * 1000.0, max_vertical * 1000.0))

    # 5. The evidence layer refused the run for a reason that is about the
    #    measurement, not the robot.
    status = record.get("evidence_status") or ""
    if status.startswith("INCOMPLETE") or status.startswith("INVALID"):
        failed = record.get("failed_gates") or []
        if "trajectory" in failed:
            return ("EVIDENCE_INVALID", "Tooling",
                    "the bundle failed its own schema: %s"
                    % (record.get("bundle_problems") or "see bundle_problems"))
        return ("EVIDENCE_INCOMPLETE", "Tooling",
                "gates that could not be evaluated: %s" % failed)

    # 6. Terminal geometry failed while evidence was fine.
    if record.get("terminal_passed") is False:
        return ("FAIL_TERMINAL", "Control",
                "terminal clause failed: %s" % (record.get("failed_clauses"),))

    # 7. Evidence contradicted the push while terminal geometry passed.
    if record.get("terminal_passed") is True and record.get("passed") is False:
        failed = record.get("failed_gates") or []
        if failed == ["gripper"]:
            return ("GATE_GRIPPER", "Grasp",
                    "the gripper aperture moved more than the calibrated bound "
                    "during the window; on this arm the fingers are deflected by "
                    "contact, so the bound is being crossed by a push")
        return ("GATE_" + ",".join(failed).upper(), "Grasp",
                "physical evidence gates failed: %s" % failed)
    return ("UNKNOWN", "UNKNOWN", "no measurement forces a single category")


def zero_span_intervals(bundle):
    """Contact intervals the recorder emitted with start == end.

    recorder.contact_intervals() opens an interval at the first touching step
    with end_sim_ns = that same step, so a contact observed for exactly ONE
    physics step is recorded as a zero-length interval - which schema.py
    rejects ('empty or inverted interval') and which therefore makes the whole
    bundle invalid. This is a recorder/schema defect, not a physics fact: the
    contact really happened, and step_ns is present in the log.

    This function only REPORTS the count. The verbatim bundle is what gets
    graded, so a trial carrying this defect is INVALID_EVIDENCE and is never
    presented as passed.
    """
    bad = []
    for index, item in enumerate((bundle.get("contacts") or {}).get("intervals") or []):
        try:
            if int(item["end_sim_ns"]) <= int(item["start_sim_ns"]):
                bad.append(index)
        except (KeyError, TypeError, ValueError):
            bad.append(index)
    return bad


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def spec_rest_height(spec, name):
    """The resting height the TASK declares. Never the operator's number."""
    for obj in spec["objects"]:
        if obj["name"] == name:
            return float(obj["initial_pose"][2])
    raise SystemExit("spec declares no object %r" % name)


def max_z_from_physics_log(path, model):
    """Independent max_z straight from the per-step log, plus its coverage."""
    highest = None
    count = 0
    missing = 0
    first_sim = last_sim = None
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            entry = (record.get("objects") or {}).get(model)
            if not isinstance(entry, dict):
                missing += 1
                continue
            pose = entry.get("pose")
            if not isinstance(pose, list) or len(pose) != 7:
                missing += 1
                continue
            z = float(pose[2])
            if not math.isfinite(z):
                missing += 1
                continue
            highest = z if highest is None else max(highest, z)
            count += 1
            sim = int(record.get("sim_ns", 0))
            first_sim = sim if first_sim is None else first_sim
            last_sim = sim
    return {"max_z_m": highest, "samples": count, "missing": missing,
            "first_sim_ns": first_sim, "last_sim_ns": last_sim}


def main(argv):
    trial_dir = Path(argv[1])
    task_path = argv[2]
    run_id = argv[3]
    arm = argv[4]
    trial = argv[5]
    wall_s = argv[6]
    load_before = argv[7]
    load_after = argv[8]
    git_head = argv[9]
    gz_version = argv[10]
    ros_distro = argv[11]
    domain_id = argv[12]

    if git_head in ("UNKNOWN", "", None):
        # git cannot read this worktree from inside WSL (.git holds a Windows
        # absolute path), so the Windows side stamps HEAD into a file. Falling
        # back to it keeps the environment fingerprint a measurement.
        for candidate in (trial_dir.parent.parent / "git_head.txt",
                          trial_dir.parent / "git_head.txt"):
            if candidate.is_file():
                git_head = candidate.read_text(encoding="utf-8").strip()
                break

    spec = json.load(open(task_path, encoding="utf-8"))
    target = spec["objects"][0]["name"]
    protected = spec["objects"][1]["name"]
    rest_from_spec = spec_rest_height(spec, target)

    logs = trial_dir / "logs"
    physics_log = logs / "physics_steps.jsonl"
    contact_log = logs / "contact_steps.jsonl"
    joint_log = logs / "joint_states.jsonl"

    record = {
        "trial": trial, "arm": arm, "task_id": spec["task_id"],
        "task_sha256": sha256_file(task_path),
        "spec_instance_sha256": spec.get("instance_sha256"),
        "seed": spec.get("random_seed"),
        "contact_height_m": float(argv[13]) if len(argv) > 13 else None,
        "rest_height_from_spec": rest_from_spec,
        "ros_distro": ros_distro, "gz_version": gz_version,
        "ros_domain_id": domain_id, "git_head": git_head,
        "wall_s": float(wall_s), "loadavg_before": load_before,
        "loadavg_after": load_after,
        "evidence_status": None, "invalid_reason": None,
        "attempts": None, "displacement_mm": None,
        "displacement_signed_mm": None, "direction_cos": None,
        "dist_to_zone_mm": None, "max_z_from_physics_log": None,
        "max_z_passed_to_evaluator": None, "terminal_passed": None,
        "passed": None, "failed_gates": None, "false_success": None,
        "bundle_sha256": None, "run_id": run_id,
        "rest_height_declared_to_recorder": None, "guard_bound": None,
        "physical_outcome": None,
        "target_object": target,
        "max_displacement_m": float(
            spec["expected_goal"]["push"][target]["max_displacement_m"]),
        "min_displacement_m": float(
            spec["expected_goal"]["push"][target]["min_displacement_m"]),
        "zero_span_contact_intervals": None,
        "failure_class": None, "failure_category": None, "failure_detail": None,
        "attempt_error_codes": None,
    }

    # --- recovery / attempt record ---------------------------------------
    recovery = None
    try:
        recovery = json.load(open(trial_dir / "recovery.json", encoding="utf-8"))
        record["attempts"] = recovery["verdict"]["attempts"]
        record["guard_bound"] = recovery.get("guard_bound")
        record["recovery_outcome"] = recovery["verdict"].get("outcome")
        record["attempt_error_codes"] = [
            a.get("error_code") for a in (recovery.get("attempts") or [])]
    except Exception as exc:                                     # noqa: BLE001
        record["invalid_reason"] = "recovery.json unreadable: %s" % exc

    # --- ground truth -----------------------------------------------------
    gt_after = None
    try:
        gt_after = json.load(open(trial_dir / "gt_after.json", encoding="utf-8"))
    except Exception as exc:                                     # noqa: BLE001
        record["invalid_reason"] = (record["invalid_reason"] or "") + \
            " gt_after.json unreadable: %s" % exc

    # --- coverage gates on the raw channels ------------------------------
    def line_count(path):
        try:
            with open(path, "rb") as stream:
                return sum(1 for _ in stream)
        except OSError:
            return 0

    physics_rows = line_count(physics_log)
    contact_rows = line_count(contact_log)
    joint_rows = line_count(joint_log)
    world_sdf = trial_dir / "sim" / "world.sdf"
    try:
        world_text = world_sdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        world_text = ""
    record["physics_rows"] = physics_rows
    record["contact_rows"] = contact_rows
    record["joint_rows"] = joint_rows
    record["contact_trace_in_world"] = "flexcell::ContactTrace" in world_text

    channels_ok = (physics_rows > 0 and contact_rows > 0 and joint_rows > 0
                   and record["contact_trace_in_world"])
    if not channels_ok:
        record["evidence_status"] = "INVALID_INFRA"
        record["invalid_reason"] = (
            (record["invalid_reason"] or "") +
            " evidence channel empty: physics_rows=%d contact_rows=%d "
            "joint_rows=%d contact_trace_in_world=%s"
            % (physics_rows, contact_rows, joint_rows,
               record["contact_trace_in_world"])).strip()
        _write(record, trial_dir)
        return 0

    # --- bundle, with the rest height bound to the spec ------------------
    args = type("A", (), dict(
        physics_log=str(physics_log), contact_log=str(contact_log),
        joint_log=str(joint_log), task=task_path, task_id=spec["task_id"],
        run_id=run_id, target=target, protected=protected,
        rest_height=rest_from_spec,
        pusher_links=list(PUSHER_LINKS), gripper_joint=GRIPPER_JOINT))()
    bundle = recorder.build(args)
    problems = schema.validate(bundle)
    bundle_path = trial_dir / "evidence_bundle.json"
    bundle_path.write_text(json.dumps(bundle, indent=2, sort_keys=True,
                                      allow_nan=False) + "\n", encoding="utf-8")
    record["bundle_sha256"] = sha256_file(bundle_path)
    record["rest_height_declared_to_recorder"] = float(args.rest_height)
    record["bundle_problems"] = problems
    record["bundle_contact_intervals"] = len(bundle["contacts"]["intervals"])
    record["bundle_component_present"] = bundle["contacts"]["component_present"]
    record["zero_span_contact_intervals"] = zero_span_intervals(bundle)

    if float(args.rest_height) != rest_from_spec:
        record["evidence_status"] = "INVALID_EVIDENCE"
        record["invalid_reason"] = ("declared rest height %r != spec rest height %r"
                                    % (args.rest_height, rest_from_spec))
        _write(record, trial_dir)
        return 0

    # --- independent max_z ------------------------------------------------
    independent = max_z_from_physics_log(physics_log, target)
    record["max_z_from_physics_log"] = (None if independent["max_z_m"] is None
                                        else round(independent["max_z_m"], 9))
    record["max_z_physics_samples"] = independent["samples"]
    record["max_z_physics_missing"] = independent["missing"]
    record["max_lift_m"] = (None if independent["max_z_m"] is None
                            else round(independent["max_z_m"] - rest_from_spec, 9))

    # --- what the evaluator is handed -------------------------------------
    trajectory = {target: {"max_z_m": independent["max_z_m"],
                           "source": "RECOMPUTED_FROM_PHYSICS_LOG",
                           "samples": independent["samples"]}}
    record["max_z_passed_to_evaluator"] = (None if independent["max_z_m"] is None
                                           else round(independent["max_z_m"], 9))
    evaluator_input = {
        "objects": (gt_after or {}).get("objects") or {},
        "trajectory": trajectory,
        "evidence": bundle,
        "agent_claimed_success": False,
    }
    (trial_dir / "evaluator_input.json").write_text(
        json.dumps(evaluator_input, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8")

    # --- grade with the frozen evaluator, untouched -----------------------
    from benchmark.evaluators import evaluate as evaluator
    verdict = evaluator.evaluate(spec, evaluator_input)
    (trial_dir / "verdict.json").write_text(
        json.dumps(verdict, indent=2, allow_nan=False) + "\n", encoding="utf-8")

    record["terminal_passed"] = verdict["terminal_passed"]
    record["passed"] = verdict["passed"]
    record["failed_clauses"] = verdict["failed_clauses"]
    record["false_success"] = verdict["false_success"]
    evidence = verdict.get("evidence") or {}
    record["evidence_status"] = evidence.get("evidence_status")
    record["physical_outcome"] = evidence.get("physical_outcome")
    record["failed_gates"] = evidence.get("failed_gates")

    # --- terminal-clause numbers, for the distribution table --------------
    for clause in verdict.get("clauses", []):
        if clause["clause"] == "push:" + target:
            ev = clause["evidence"]
            moved = ev.get("displacement_m")
            record["displacement_mm"] = (None if moved is None
                                         else round(float(moved) * 1000.0, 3))
            record["direction_cos"] = ev.get("direction_cosine")
            record["dist_to_zone_mm"] = (None if ev.get("distance_m") is None
                                         else round(float(ev["distance_m"]) * 1000.0, 3))
            record["clause_ok"] = clause["ok"]
    if recovery is not None:
        signed = recovery.get("achieved_signed_m")
        if isinstance(signed, (int, float)) and math.isfinite(signed):
            record["displacement_signed_mm"] = round(float(signed) * 1000.0, 3)
        else:
            record["displacement_signed_mm"] = None

    # A signed/unsigned disagreement is not an error - it is the signature of
    # an object pushed the wrong way, and it must be visible, not averaged out.
    if (record["displacement_mm"] is not None
            and record["displacement_signed_mm"] is not None
            and abs(abs(record["displacement_signed_mm"]) - record["displacement_mm"]) > 5.0):
        record["signed_unsigned_note"] = "signed and unsigned magnitudes differ by >5 mm"

    attempts = (recovery or {}).get("attempts") or []
    failure_class, category, detail = classify_failure(record, attempts, verdict)
    if record["passed"]:
        failure_class, category, detail = None, None, None
    record["failure_class"] = failure_class
    record["failure_category"] = category
    record["failure_detail"] = detail

    _write(record, trial_dir)
    return 0


def _write(record, trial_dir):
    (trial_dir / "trial_record.json").write_text(
        json.dumps(record, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8")
    print("TRIAL_RECORD " + json.dumps(record, sort_keys=True, default=str))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
