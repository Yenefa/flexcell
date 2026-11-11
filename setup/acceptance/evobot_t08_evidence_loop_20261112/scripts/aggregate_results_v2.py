#!/usr/bin/env python3
"""Post-freeze reporting pass: the final results table, with exclusion reasons.

WHY A SECOND REPORTING SCRIPT EXISTS
    aggregate_results.py is one of the 16 files covered by the pre-U freeze, and
    I edited it after arm U to add nested-arm support and an invalid_reason
    column. verify_freeze.py caught it. Rather than redefine the freeze to fit
    the edit (which would make the freeze worthless), the edit was reverted and
    this separate post-freeze script was written instead.

    This file is NOT part of the trial pipeline. It only reads trial_record.json
    files that already exist and was written after all Gazebo runs finished, so
    it cannot influence any measured value. The frozen script remains byte
    identical to its pre-U hash; this one is deliberately not in the freeze list
    because it cannot change a measurement.

WHAT IT ADDS OVER THE FROZEN VERSION
    - nested arms (U/seed3000/t1) as well as flat arms (R/t1)
    - invalid_reason on every trial whose evidence was not usable, so an
      unmeasurable trial is never mistaken for a measured failure
    - counts_toward_denominator, so the pass-rate arithmetic is visible
    - a per-arm failure-mode tally and a round-wide tally
"""
import json
import re
import sys
from pathlib import Path

WT = Path("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp")


def spec_path_for(task_id):
    """Where the instance this trial claims to have run actually lives."""
    match = re.search(r"seed(\d+)$", task_id or "")
    if not match:
        return None
    seed = int(match.group(1))
    split = "t08_unseen" if seed >= 3000 else "t08_dev"
    path = WT / "benchmark" / "tasks" / split / ("%s.json" % task_id)
    return path if path.is_file() else None

COLUMNS = [
    "trial", "task_id", "arm", "seed", "attempts", "recovery_outcome",
    "displacement_mm", "displacement_signed_mm", "direction_cos",
    "dist_to_zone_mm", "max_lift_m", "max_z_from_physics_log",
    "max_z_passed_to_evaluator", "terminal_passed", "passed",
    "evidence_status", "physical_outcome", "failed_gates", "failed_clauses",
    "failure_class", "failure_category", "guard_bound", "false_success",
    "bundle_sha256", "run_id", "task_sha256",
    "rest_height_from_spec", "rest_height_declared_to_recorder",
    "contact_height_m", "contact_rows", "physics_rows", "joint_rows",
    "zero_span_contact_intervals", "wall_s", "loadavg_before", "loadavg_after",
    "git_head", "gz_version", "ros_distro", "ros_domain_id",
    "invalid_reason", "bundle_problems", "counts_toward_denominator",
    "failure_class_rechecked", "bounds_violated", "spec_vs_world_offset_m",
    "arm_instance",
]


def cell(value):
    if value is None:
        return "MISSING"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "|".join(str(v) for v in value) if value else "-"
    if isinstance(value, float):
        return ("%.6f" % value).rstrip("0").rstrip(".")
    return str(value).replace("\t", " ").replace("\n", " ")


def _recheck(record, trial_dir):
    """Re-derive bound violations from the frozen verdict.json clause evidence.

    WHY THIS EXISTS, AND WHY IT IS NOT AN EDIT TO THE TRIAL PIPELINE
        The trial-time classifier assigns ONE failure class, checking causes in
        a fixed order. For S/t1 it reported FAIL_ZONE while the clause evidence
        shows the displacement also exceeded the frozen 150 mm ceiling
        (176.28 mm) - both bounds were violated and the reported class named
        only one. Rather than edit build_trial_evidence.py (which is inside the
        pre-U freeze) and re-run the classifier over already-measured trials,
        this post-freeze reporting pass reads the FROZEN verdict.json clause
        evidence and lists every bound that was violated. The trial-time class
        is kept alongside it so the difference is visible instead of erased.
    """
    verdict_path = trial_dir / "verdict.json"
    if not verdict_path.is_file():
        return
    verdict = json.loads(verdict_path.read_text(encoding="utf-8"))
    target = record.get("target_object") or "target_box_a"
    clause = None
    for item in verdict.get("clauses", []):
        if item["clause"] == "push:" + target:
            clause = item.get("evidence") or {}
    violated = []
    if clause:
        moved = clause.get("displacement_m")
        if isinstance(moved, (int, float)):
            if moved < float(clause.get("min_displacement_m") or 0.030):
                violated.append("displacement_below_min")
            if moved > float(clause.get("max_displacement_m") or 0.150):
                violated.append("displacement_above_max")
        vertical = clause.get("vertical_m")
        if (isinstance(vertical, (int, float))
                and vertical > float(clause.get("max_vertical_m") or 0.020)):
            violated.append("vertical_above_max")
        cos = clause.get("direction_cosine")
        if (isinstance(cos, (int, float))
                and cos < float(clause.get("min_direction_cosine") or 0.9)):
            violated.append("direction_cosine_below_min")
        if clause.get("inside_zone") is False:
            violated.append("outside_zone")
        lift = clause.get("max_lift_m")
        allowed = clause.get("max_lift_allowed_m")
        if (isinstance(lift, (int, float)) and isinstance(allowed, (int, float))
                and lift > allowed):
            violated.append("lift_above_max")
    # The unmoved clause is graded against the SPEC's declared start pose. When
    # the world spawned the object somewhere else, that clause fails without the
    # object having moved at all - so the world-basis motion is checked here
    # before calling anything disturbed. Otherwise a spec-vs-world mismatch is
    # recorded as a robot failure, which is the exact misclassification this
    # batch exists to prevent.
    before_path = trial_dir / "gt_before.json"
    after_path = trial_dir / "gt_after.json"
    if before_path.is_file() and after_path.is_file():
        before = json.loads(before_path.read_text(encoding="utf-8")).get("objects") or {}
        after = json.loads(after_path.read_text(encoding="utf-8")).get("objects") or {}
        for item in verdict.get("clauses", []):
            if not item["clause"].startswith("unmoved:") or item.get("ok") is not False:
                continue
            name = item["clause"].split(":", 1)[1]
            if name not in before or name not in after:
                violated.append("protected_object_unobserved")
                continue
            moved = ((after[name][0] - before[name][0]) ** 2
                     + (after[name][1] - before[name][1]) ** 2) ** 0.5
            record["protected_world_motion_m"] = round(moved, 6)
            if moved > 0.005:
                violated.append("protected_object_disturbed")
            else:
                violated.append("protected_object_unmoved_in_world"
                                "(clause failed only on spec-vs-world offset)")
    record["bounds_violated"] = violated

    # Does the world that actually ran match the task instance it is graded
    # against? If not, the trial did not run the declared task at all and no
    # pass/fail from it can be attributed to the instance.
    spec_path = record.get("_spec_path")
    before_path = trial_dir / "gt_before.json"
    if spec_path and Path(spec_path).is_file() and before_path.is_file():
        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        before = json.loads(before_path.read_text(encoding="utf-8")).get("objects") or {}
        worst = 0.0
        for obj in spec.get("objects", []):
            name = obj["name"]
            if name not in before:
                continue
            want = obj["initial_pose"]
            have = before[name]
            worst = max(worst, ((want[0] - have[0]) ** 2
                                + (want[1] - have[1]) ** 2) ** 0.5)
        record["spec_vs_world_offset_m"] = round(worst, 6)
        if worst > 0.001:
            record["counts_toward_denominator"] = False
            record["invalid_reason"] = (
                "ENVIRONMENT: the world that ran spawned the objects at the "
                "seed-2000 geometry, not this instance's declared poses "
                "(largest spec-vs-world offset %.1f mm). sim_profile.py takes no "
                "object-pose argument and no step in the pipeline applies "
                "spec.objects[].initial_pose, so this task instance was never "
                "instantiated; its verdict is not a measurement of it."
                % (worst * 1000.0))
            record["failure_class_rechecked"] = "INVALID_ENVIRONMENT"


def trial_dirs(arm_dir):
    """Flat (R/t1) and nested (U/seed3000/t1) arm layouts, both supported."""
    for candidate in sorted(p for p in arm_dir.iterdir() if p.is_dir()):
        if (candidate / "trial_record.json").is_file():
            yield candidate
            continue
        for nested in sorted(p for p in candidate.iterdir() if p.is_dir()):
            if (nested / "trial_record.json").is_file():
                yield nested


def main(argv):
    evidence_root = Path(argv[1])
    out_path = Path(argv[2])
    arms = argv[3:] or ["R", "S", "U", "U_shot"]
    rows = []
    for arm in arms:
        arm_dir = evidence_root / arm
        if not arm_dir.is_dir():
            continue
        for trial_dir in trial_dirs(arm_dir):
            record = json.loads(
                (trial_dir / "trial_record.json").read_text(encoding="utf-8"))
            # Nested layouts carry the census sub-arm in the record already
            # ("U/seed3000"); grouping must still happen at the top-level arm or
            # the unseen rows never appear in the per-arm summary.
            record["arm_instance"] = str(trial_dir.relative_to(evidence_root))
            record["arm"] = arm
            record["counts_toward_denominator"] = True
            record["failure_class_rechecked"] = None
            record["bounds_violated"] = None
            record["spec_vs_world_offset_m"] = None

            # An unusable bundle means every evidence gate was unevaluable, so
            # the trial's pass/fail is not a measurement of the robot. It is
            # excluded from the denominator WITH ITS REASON, never silently
            # dropped and never counted as a robot failure.
            if record.get("zero_span_contact_intervals"):
                record["counts_toward_denominator"] = False
                record["invalid_reason"] = (
                    "recorder emitted zero-length contact interval(s) %s; "
                    "schema rejected the bundle so all nine gates were "
                    "unevaluable. TOOLING defect, not a robot failure. Terminal "
                    "clause still evaluated independently on ground truth."
                    % record["zero_span_contact_intervals"])
            elif str(record.get("evidence_status") or "").startswith("INVALID"):
                record["counts_toward_denominator"] = False
                if not record.get("invalid_reason"):
                    record["invalid_reason"] = "invalid evidence bundle"
            record["_spec_path"] = str(spec_path_for(record.get("task_id")) or "")
            _recheck(record, trial_dir)
            rows.append(record)

    with out_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\t".join(COLUMNS) + "\n")
        for row in rows:
            stream.write("\t".join(cell(row.get(c)) for c in COLUMNS) + "\n")
    print("wrote %d rows to %s" % (len(rows), out_path))

    for arm in arms:
        arm_rows = [r for r in rows if r.get("arm") == arm]
        if not arm_rows:
            continue
        counted = [r for r in arm_rows if r.get("counts_toward_denominator")]
        excluded = [r for r in arm_rows if not r.get("counts_toward_denominator")]
        term = sum(1 for r in counted if r.get("terminal_passed") is True)
        passed = sum(1 for r in counted if r.get("passed") is True)
        complete = sum(1 for r in counted
                       if r.get("evidence_status") == "COMPLETE")
        print("%s: n=%d counted=%d excluded=%d terminal_passed=%d/%d "
              "passed=%d/%d evidence_COMPLETE=%d"
              % (arm, len(arm_rows), len(counted), len(excluded),
                 term, len(counted), passed, len(counted), complete))
        modes = {}
        for row in counted:
            key = row.get("failure_class") or "PASS"
            modes[key] = modes.get(key, 0) + 1
        if modes:
            print("   failure modes: %s" % ", ".join(
                "%s=%d" % (k, v) for k, v in sorted(modes.items())))
        for row in excluded:
            print("   EXCLUDED %s: %s" % (row.get("trial"), row.get("invalid_reason")))
        disp = [float(r["displacement_mm"]) for r in counted
                if isinstance(r.get("displacement_mm"), (int, float))]
        if disp:
            ordered = sorted(disp)
            print("   displacement_mm min=%.1f median=%.1f max=%.1f spread=%.1f"
                  % (ordered[0], ordered[len(ordered) // 2], ordered[-1],
                     ordered[-1] - ordered[0]))

    # Round-wide failure-mode tally over counted trials only.
    tally = {}
    for row in rows:
        if not row.get("counts_toward_denominator"):
            continue
        key = row.get("failure_class") or "PASS"
        tally[key] = tally.get(key, 0) + 1
    total = sum(tally.values())
    print("ROUND VALID-TRIAL FAILURE TALLY (n=%d): %s"
          % (total, ", ".join("%s=%d" % (k, v) for k, v in sorted(tally.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
