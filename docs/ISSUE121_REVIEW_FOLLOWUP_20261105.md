# Issue #121 — production geometry and refusal regressions

Continuation of [PR #122](https://github.com/Yenefa/flexcell/pull/122), based on
`a86fc5d0379c7bb1a13994ff8db2312083e3cb7b`. This is a code and offline-test
follow-up; it does not add a physical acceptance window.

## Remaining negative-control defect

The upstream fix strengthens `expected_failure`, but a successful placement
still satisfies the separate `succeeded` predicate. A synthetic run through the
actual upstream `sim_smoke.main()` reproduces the problem:

| `--case gate_refusal`, successful release + verification | Upstream base | Follow-up |
| --- | --- | --- |
| Exit code | 0 | 1 |
| Status | `PASS` | `ROBOT_FAILURE` |
| `expectation_met` | `true` | absent |
| Subsequent reset | dispatched | not dispatched |

All subprocesses and delays in this reproduction are mocked. These are harness
observations, not robot results. The regression now exercises the real runner.

Acceptance requires the task client's expected failure exit (1), typed task
failure, `object_at_place=false`, exactly one matching-object PLACE failure
(`ERR_PLACE_FAILED`), an explicit attitude-gate refusal, no release confirmation
in any skill record and no VERIFY call. Successful releases, unrelated errors,
duplicate/missing records, wrong object identities and abnormal process exits
cannot satisfy this negative control.

## Test the solver that production actually uses

The closed-form geometry is extracted into `level_release_ik.hpp`, which the
planner calls directly. The helper corrects the lateral yaw sign, enumerates
both yaw branches, wraps yaw and shoulder angles, and computes link constants
from the existing URDF dimensions without rounded trigonometric constants.

Pitch candidates cover the sum of the actual three joint-limit intervals.
The analytically best pitch for the measured box up-vector is included and
tried first; the remaining deterministic grid and interval endpoints follow
in order of box attitude. This retains large-rotation solutions and useful
candidates when enumeration has a bounded time budget. The fallback and chosen
joint-goal plan both receive only the remaining stage time.

The planner retains its model-FK check, 1 mm position gate, joint limits,
collision check and upstream trajectory planner. The opt-in defaults and the
release-gate configuration checks introduced by `a86fc5d` are retained.

Six GTest cases compare the production helper against independent serial-chain
FK: both lateral-offset signs, ±60° and 170° attachment rotations, the review's
60° counterexample, 2,000 seeded feasible joint vectors, deterministic pitch
ordering and impossible lateral displacement. These check kinematic geometry;
they do not establish collision-free planning or physical placement quality.
The test is registered in the existing `flexcell_mtc` CMake test suite.

## Verification and limits

- Host C++17 build with `-Wall -Wextra -Werror`: 6/6 GTests pass.
- ROS-independent Python suite: 849 pass, plus three subtests. Fourteen files
  requiring ROS modules or generated messages, including indirect Jev fixtures,
  are excluded explicitly from this host run.
- All 50 targeted refusal, evidence, attitude and seed cases pass, including
  the 19 refusal-runner cases with final cross-skill release checks.
- Attribute scan: 45 files, zero problems; `git diff --check` passes.
- Full simulation image build: stopped during dependency download (exit 130).
  Installation requires another 3,342 MB; only about 0.9 GB remained at that
  point. No Jazzy/MoveIt integration test, Gazebo window or GitHub Actions result
  is claimed for this follow-up.

On a provisioned Jazzy host, rebuild the changed MTC package, run
`colcon test --packages-select flexcell_mtc flexcell_skills`, then inspect
`colcon test-result --verbose`. A new live window must use the rebuilt binary
and its own source/configuration fingerprint. Previous PR #122 measurements
belong to their recorded versions and do not qualify this changed solver.
