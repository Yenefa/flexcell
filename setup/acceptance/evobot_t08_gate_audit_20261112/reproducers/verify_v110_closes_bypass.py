#!/usr/bin/env python3
"""Prove verify.py v1.1.0 closes the F1 bypass that v1.0.0 admits."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(WT, "benchmark", "evidence"))
sys.path.insert(0, os.path.join(HERE, "..", "patches"))
sys.path.insert(0, WT)

import fixtures
import schema
import verify as v100
import verify_v1_1_0 as v110

SPEC = os.path.join(WT, "benchmark", "tasks", "t08_dev", "T08-push-seed2000.json")
REST = 0.0175
STEP = 5000000
T0 = 10000000000
N = 40
ALLOWED = ["open_manipulator_x::gripper_left_link::gripper_left_link_collision",
           "open_manipulator_x::gripper_right_link::gripper_right_link_collision"]
LIMITS = {"max_lift_during_m": 0.020, "max_aperture_change_rad": 0.002,
          "protected_move_m": 0.005}


def load_spec():
    with open(SPEC, encoding="utf-8") as f:
        return json.load(f)


def carried(rest_declared, carry_z, run_id="t08loop-fixture-t1"):
    b = fixtures.base_bundle()
    b["objects"] = {
        "target_box_a": {"role": "target", "samples": None, "sample_count": N,
                         "dropped_samples": 0, "max_gap_ns": STEP},
        "target_box_b": {"role": "protected", "samples": None, "sample_count": N,
                         "dropped_samples": 0, "max_gap_ns": STEP},
    }
    b["task"].update(target_object="target_box_a",
                     protected_object="target_box_b",
                     rest_height_m=rest_declared, task_id="T08-push-seed2000",
                     task_sha256=schema.sha256_file(SPEC))
    b["objects"]["target_box_a"]["samples"] = fixtures.trajectory(
        T0, N, carry_z, 0.22, -0.003)
    prot = fixtures.trajectory(T0, N, REST, 0.0, 0.0)
    b["objects"]["target_box_b"]["samples"] = [
        [q[0], q[1], q[2], 0.20, -0.18, REST] + q[6:] for q in prot]
    b["gripper"]["span"] = [[1000000000 + STEP * i, 0.0] for i in range(N)]
    b["contacts"].update(pusher_links=[ALLOWED[1]],
                         intervals=[{"start_sim_ns": T0 + STEP * 5,
                                     "end_sim_ns": T0 + STEP * 39,
                                     "other": ALLOWED[1]}])
    b["attachment"] = {"events": 0, "attached_during_window": False}
    b["run"]["run_id"] = run_id
    b["run"]["execution_window"] = {"start_sim_ns": T0,
                                    "end_sim_ns": T0 + STEP * (N - 1),
                                    "start_mono_ns": 1000000000,
                                    "end_mono_ns": 1000000000 + STEP * (N - 1)}
    b["teleport"]["max_single_step_jump_m"] = v100._observed_max_jump(b)
    b["manifest"]["bundle_sha256"] = schema.bundle_sha256(b)
    return b


def main():
    print("=" * 78)
    print("v1.0.0 vs v1.1.0 on the F1 carry-as-push bypass")
    print("=" * 78)
    spec = load_spec()
    term = fixtures.terminal_verdict(True)
    checks = []

    def show(label, b, want100, want110, run_id=None, allowed=ALLOWED):
        r100 = v100.verify(b, term, LIMITS)
        r110 = v110.verify(b, term, LIMITS, spec=spec, spec_path=SPEC,
                           expected_run_id=run_id or b["run"]["run_id"],
                           allowed_pusher_links=allowed)
        ok = (r100["passed"] == want100) and (r110["passed"] == want110)
        checks.append(ok)
        print("  %-44s v1.0.0=%-5s v1.1.0=%-5s %s"
              % (label, r100["passed"], r110["passed"],
                 "OK" if ok else "UNEXPECTED"))
        if not ok:
            print("     v1.0.0 gates:", r100["failed_gates"])
            print("     v1.1.0 gates:", r110["failed_gates"])
            print("     v1.1.0 reason:", r110["failure_reason"])
        return r110

    print()
    print("THE BYPASS - object carried 50 mm above the table, rest declared as")
    print("the carry height:")
    show("carry 50mm, rest=self-declared",
         carried(REST + 0.050, REST + 0.050), True, False)

    print()
    print("THE CONTROL - identical motion, rest declared honestly:")
    show("carry 50mm, rest=spec", carried(REST, REST + 0.050), False, False)

    print()
    print("THE POSITIVE - a genuine push at rest height:")
    show("honest push at rest", carried(REST, REST), True, True)

    print()
    print("REPLAY - bundle captured for a different run:")
    show("replayed bundle, wrong run_id",
         carried(REST, REST, run_id="some-other-run"), True, False,
         run_id="t08loop-R-t1")

    print()
    print("INTEGRITY - bundle edited after sealing:")
    b = carried(REST, REST)
    b["run"]["run_id"] = "edited-after-seal"
    show("edited bundle, stale digest", b, True, False,
         run_id="edited-after-seal")

    print()
    print("PUSHER ALLOW-LIST - the floor declared as the pusher:")
    b = carried(REST, REST)
    floor = "ground_plane::link::collision"
    b["contacts"]["pusher_links"] = [floor]
    b["contacts"]["intervals"] = [{"start_sim_ns": T0,
                                   "end_sim_ns": T0 + STEP * 39,
                                   "other": floor}]
    b["manifest"]["bundle_sha256"] = schema.bundle_sha256(b)
    show("floor as pusher", b, True, False)

    print()
    print("GRIPPER - single-sample span:")
    b = carried(REST, REST)
    b["gripper"]["span"] = [[1000000000, 0.0]]
    b["manifest"]["bundle_sha256"] = schema.bundle_sha256(b)
    show("one-sample gripper span", b, True, False)

    print()
    print("=" * 78)
    bad = sum(1 for c in checks if not c)
    print("  %d checks, %d as expected, %d UNEXPECTED"
          % (len(checks), len(checks) - bad, bad))
    print("  v1.1.0 rejects the F1 bypass, keeps the honest push, and refuses")
    print("  replay / stale digest / floor-as-pusher / one-sample gripper.")
    print("=" * 78)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
