#!/usr/bin/env python3
"""Assemble results.tsv from per-trial records, and refuse to invent a number.

WHY THIS IS A SEPARATE STEP
    Every column below is copied from a trial_record.json that was produced by
    build_trial_evidence.py from that trial's own files. Nothing here computes a
    verdict; if a record is missing, the row is written with MISSING in every
    measurement column rather than with a plausible default.

FOUR STATES, KEPT SEPARATE
    planning_correct       did the driver ask for a request the policy implies
    execution_succeeded    did the push physically deliver the requested motion
    independent_evaluation_passed   evaluate.py v0.5.0 passed=true
    agent_claimed_success  always false here: this batch never claims success
    They are separate columns because a run can succeed at one and fail the next,
    and collapsing them is how "the robot did it" gets asserted from "the code
    ran".
"""
import json
import sys
from pathlib import Path

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
]


def cell(value):
    if value is None:
        return "MISSING"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return "|".join(str(v) for v in value) if value else "-"
    if isinstance(value, float):
        return ("%.6f" % value).rstrip("0").rstrip(".") if value == value else "nan"
    return str(value).replace("\t", " ").replace("\n", " ")


def main(argv):
    evidence_root = Path(argv[1])
    out_path = Path(argv[2])
    arms = argv[3:] or ["R", "S", "U"]
    rows = []
    for arm in arms:
        arm_dir = evidence_root / arm
        if not arm_dir.is_dir():
            continue
        for trial_dir in sorted(arm_dir.iterdir()):
            if not trial_dir.is_dir():
                continue
            record_path = trial_dir / "trial_record.json"
            if not record_path.is_file():
                rows.append({c: "MISSING" for c in COLUMNS} | {
                    "trial": trial_dir.name, "arm": arm,
                    "evidence_status": "INVALID_INFRA"})
                continue
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record.setdefault("arm", arm)
            # An INVALID_INFRA trial is excluded from the pass-rate denominator,
            # but the exclusion is written into the table rather than applied
            # silently: a reader must be able to see which trials were dropped
            # and why, or a denominator becomes a place to hide a failure.
            record["counts_toward_denominator"] = not (
                str(record.get("evidence_status") or "").startswith("INVALID"))
            rows.append(record)

    with out_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("\t".join(COLUMNS) + "\n")
        for row in rows:
            stream.write("\t".join(cell(row.get(c)) for c in COLUMNS) + "\n")
    print("wrote %d rows to %s" % (len(rows), out_path))

    # A short, honest summary per arm. Counts, then the distribution, because
    # with n=5 a pass-rate difference is not statistically distinguishable and
    # the distribution is where the real signal is.
    for arm in arms:
        arm_rows = [r for r in rows if r.get("arm") == arm]
        if not arm_rows:
            continue
        def numbers(key):
            return [float(r[key]) for r in arm_rows
                    if isinstance(r.get(key), (int, float))
                    and not isinstance(r.get(key), bool)]
        disp = numbers("displacement_mm")
        term = sum(1 for r in arm_rows if r.get("terminal_passed") is True)
        passed = sum(1 for r in arm_rows if r.get("passed") is True)
        complete = sum(1 for r in arm_rows
                       if r.get("evidence_status") == "COMPLETE")
        counted = [r for r in arm_rows if r.get("counts_toward_denominator")]
        excluded = [r for r in arm_rows if not r.get("counts_toward_denominator")]
        print("%s: n=%d counted=%d excluded=%d terminal_passed=%d passed=%d "
              "evidence_COMPLETE=%d"
              % (arm, len(arm_rows), len(counted), len(excluded), term, passed,
                 complete))
        for row in excluded:
            print("   EXCLUDED %s: %s" % (row.get("trial"), row.get("invalid_reason")))
        modes = {}
        for row in counted:
            key = row.get("failure_class") or "PASS"
            modes[key] = modes.get(key, 0) + 1
        if modes:
            print("   failure modes: %s" % ", ".join(
                "%s=%d" % (k, v) for k, v in sorted(modes.items())))
        if disp:
            disp_sorted = sorted(disp)
            median = disp_sorted[len(disp_sorted) // 2]
            print("   displacement_mm min=%.1f median=%.1f max=%.1f spread=%.1f"
                  % (disp_sorted[0], median, disp_sorted[-1],
                     disp_sorted[-1] - disp_sorted[0]))
        for row in arm_rows:
            print("   %s: terminal=%s passed=%s evidence=%s failure=%s"
                  % (row.get("trial"), row.get("terminal_passed"),
                     row.get("passed"), row.get("evidence_status"),
                     row.get("failure_class")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
