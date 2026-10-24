# 2026-10-21 — DESKTOP-8JBM0GF bring-up evidence (M2 ladder + S7 track)

Machine: `DESKTOP-8JBM0GF` (Win10 22H2, RTX 4060 Ti 16GB), WSL2 Ubuntu-24.04,
ROS 2 Jazzy, Gazebo Harmonic 8.15.0, MoveIt 2.12.4.
Base: `main` @ `a9b6a62`. Branch under test: `fix/pick-lift-release`
(`c15187d` typed-code detail, `110ae98` pick lift release, `011bb09` S7 envelope).

Runtime: `setup/102_mainline_runtime.sh cold fsm 0.7` with
`FLEXCELL_CARRY_BACKEND=velocity_servo` and
`FLEXCELL_WORLD=worlds/flexcell_velocity_servo` (see notes below).

## Why the whole ladder was re-run here

This was a fresh machine: the WSL distro, ROS, the workspace and the
`flexcell_gazebo` carry plugin were all built from scratch on 2026-10-16/21.
Two host-specific facts had to be discovered and are recorded here because
they silently change results:

1. **The `teleport` carry backend cannot hold a box on this host.**
   `set_pose` returns true (p50 latency 0.4 ms) but does not reset body
   velocity, so between two 10 Hz pins the box free-falls faster and faster.
   Every pick ended `ERR_GRASP_FAILED` (`box did not follow the lift`,
   rise ~0.017-0.026 m against a 0.030 m threshold). With
   `carry_backend=velocity_servo` (+ `worlds/flexcell_velocity_servo.sdf`)
   the referee reports `box_rise 0.098 m`, `zone_error 0.008 m`.
2. **`setup/flexcell start` writes no deployment fingerprint.**
   `setup/94_scenario_runner.py` then stops the batch with
   `missing or mixed runtime fingerprints within batch`. Use
   `setup/102_mainline_runtime.sh cold ...` for anything the runner drives.

## Results

| Step | Command | Result |
| --- | --- | --- |
| start | `setup/flexcell start` | `START OK`, 17/17 checks, `hard_fail: []` |
| reset | `setup/flexcell reset` | `"ok": true`, both boxes canonical, carry disengaged |
| referee | `setup/92_referee.py --object target_box_a --zone 0.12 -0.15 0.0175 --demo` | `CONSISTENT` (box_rise 0.0984 m, zone_error 0.0079 m) |
| week-1.5 | `setup/61_w15_acceptance.sh all` | `GATE: ALL PASS` 14/14 |
| day-2 | `setup/32_day2_acceptance.sh ...` (10 cases) | `GATE: ALL PASS` 17/17 |
| M2 smoke | `94_scenario_runner.py --batch S1:5 S2:5 S4:5 S5:5 --stage smoke` | `PASS` (S1 5/5, S2 5/5, S4/S5 fail-as-expected) |
| M2 baseline | `94_scenario_runner.py --batch S1:10 S2:5 S4:5 S5:5 --stage baseline` | `PASS` (25/25 as expected, S1 10/10 CI95 [0.72, 1.00]) |
| S7 smoke | `--batch S7:5 --stage smoke` | 4/5 before the two fixes, 5/5 after |
| S7 baseline | `--batch S7:10 --stage baseline --smoke-summary <S7 5/5 batch>` | `PASS` 10/10, CI95 [0.72, 1.00] |

Artifacts in this directory: `week15_battery_c15187d_20261021_102224/` is the
post-fix Week-1.5 session (the code under test); `s7_batches/` holds the raw
scenario-runner batch summaries (4/5 pre-fix, the seed-20260931 reproduction,
5/5 after, and the 10/10 baseline).

## The two defects S7 exposed and this branch fixes

* `pick_server`: a non-cancel **lift** motion failure returned without
  releasing the carry servo. `ERR_MOTION_FAILED` (30) is a recoverable class,
  so FSMPolicy retried — and the retry was rejected by the safety gate as
  `already_carried`, surfacing `ERR_SAFETY_REJECTED` instead of the cause.
  After `110ae98` the same seed ends `ERR_RECOVERY_EXHAUSTED` with both
  attempts `ERR_MOTION_FAILED` and the trace shows the retry running.
* `96_s7_perturb.py`: the placement envelope allowed `y = -0.226 m`, which is
  graspable but whose lift pose (grasp + 0.10 m) has no IK solution — the probe
  measured kinematics, not adaptation. `011bb09` tightens the envelope to
  `x in [0.17, 0.26]`, `y in [-0.185, 0.16]` (measured, to be replaced by an
  IK filter under #9).

Also on this branch: `c15187d` restores the typed skill code in the PLACE abort
detail (`error_codes.error_name()`), which is what the week15 `invalid_typed`
gate needs; the frozen task-level taxonomy (50/51) is untouched.
