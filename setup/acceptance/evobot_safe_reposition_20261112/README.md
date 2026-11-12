# T08 opt-in reposition candidate — 2026-11-12

**Single development-instance candidate: full task acceptance PASS (9/9).**
**Ordinary-task regression: NOT CLEARED. Formal baseline: NOT PROMOTED.**

The development plan is `docs/T08_DEVELOPMENT_PLAN_20261112.md`; public stage
tracker [#235](https://github.com/Yenefa/flexcell/issues/235), Junior work
[#231](https://github.com/Yenefa/flexcell/issues/231),
[#232](https://github.com/Yenefa/flexcell/issues/232),
[#233](https://github.com/Yenefa/flexcell/issues/233),
[#234](https://github.com/Yenefa/flexcell/issues/234).

## Implemented change

An opt-in `push_server` motion adapter replaces low APPROACH/RETREATING transfers
with **LIFT → TRANSFER → LOWER**. It reads fresh composed world→EE poses, verifies
measured clearance before lateral transit, and refuses further commands after
failed motion, insufficient height, unavailable state, unconfirmed carry state or
cancellation. It records intended/actual waypoints and object poses before/after
each reposition. Existing push targets, stroke logic and task criteria are unchanged.

`safe_reposition_enabled` defaults **false**. `contracts/push.py`, nine frozen
files, TaskSpec, gripper limit and installed/shared packages are byte-identical.
New Python is exercised through a read-only source overlay, not installed into
the formal baseline. Pure adapter/node tests and existing push suites passed
(74 checks; the read-only pytest cache produced warnings, not test failures).

Pinned collision meshes bound link5 and gripper geometry about EE at 147.791 mm.
With a 35 mm object top, 5 mm geometric margin and the unchanged 20 mm tracking
tolerance: required **measured** transit z = 187.791 mm; commanded z = 207.791 mm.
The eight measured lift/transfer endpoints were at least **199.465 mm**.
This is a tool-envelope endpoint check, not a proof of forearm or continuously
swept-path collision clearance. Calibration is for the world frame and this robot.

## Preregistered physical pair

One fresh control and one candidate execution, dev seed2000, contact height
0.0200 m, requested recovery target 0.0900 m, at most two pushes. Same image,
native libraries, masses/friction, physics timestep and TaskSpec. Copied world
SHA256 is identical: `41aaada28216c028e8552fffc1971cf8b37d84594a16fbccc6de2fead0bc92f9`.
Both worlds have the same observational contact sensors and native step logging.

| Observation | Original control | Candidate |
| --- | --- | --- |
| Final signed displacement along requested −x | **−63.655 mm** | **+110.145 mm** |
| Full independent acceptance | False | **True, all 9 gates** |
| Native physics steps per object | 5,185 | 7,401 |
| Missing trajectory samples | 0 | 0 |
| Raw step spacing | consecutive 5 ms | consecutive 5 ms |
| Protected blue net displacement | 0.0 m | 0.0 m |
| Peak red lift | 27.051 mm | **3.350 mm** |
| Gripper travel (URDF prismatic joint) | 0.701 mm | 1.583 mm, under unchanged 2 mm limit |
| Physical attachment | 0 events | 0 events |

The candidate's first retreat moved the box **2.657 mm further forward**; its
second retreat moved it **0.625 mm backwards**, within the preregistered 5 mm
intermediate return-loss gate. All four reposition routes executed the declared
three-waypoint order. Raw phase events, all Push logs, MoveToPose endpoints,
WorldState, contacts, joint states and native physics logs are retained.

**This is not a success-rate or superiority estimate.** One control/candidate pair
does not separate stochastic contact variance from every treatment effect, nor
establish repeatability or generalization. It demonstrates the actual candidate
return path and one complete independently graded task. Earlier T08 passes already
exist; this is not claimed as the project's first push or first full pass.

## Important limits, kept separate from task acceptance

Both individual PushObject calls still returned FAILED: first contact loss, then
an overshoot of approximately **17.5 mm** beyond the second requested 73.2 mm.
The final task can satisfy its broader frozen 30–150 mm/zone clauses while a
particular requested stroke fails its own bounded-push contract. Those outcomes
must not be relabeled. The old recovery driver reports `achieved=107.524 mm`,
whereas measured final net motion is 110.145 mm; returned-state closed-loop
accounting and bounded finishing remain next-stage work.

The probe did not supply an Agent success claim to the evaluator. Its raw
`false_failure=true` on the passing candidate is therefore a missing-claim probe
artifact, **not evidence that an Agent misjudged the task**. False Success/claim
accuracy was not measured here; a default false flag is not a measured zero rate.

## Failed acquisition retained

The first candidate session was blocked before any push: zero WorldState samples
and a pending Observe goal response. It remains `candidate/`, classified
**INVALID_INFRA, zero physical push attempts**. No result was replaced.

`HARNESS_RETRY1.md` records the diagnosis and acquisition-only retry: the outer
deadline had cut short the recorder's own request timeout. The retry uses its own
ROS domain/partition/output and a longer outer readiness budget; the unanswered
goal's underlying cause remains UNKNOWN. Motion source/parameters were unchanged.
`run_arm.v1.py`, both preexecution records and the original failure are preserved.

## Existing-task regression blocks promotion

One candidate-overlay ordinary pick/place task and one original-source diagnostic
both failed at PLACE with error 25. Both confirmed carry release but the gripper
did not open: `reached_goal=false`, `stalled=true`, `GRASP_STALLED`, about 31 mm
aperture error. PICK succeeded in both. Identity audits have zero mismatches;
place/pick/carry/common/task executor source is unchanged from the original.

This reproduces the previously documented release blocker on original source;
it does not prove universal causal non-regression or permit discarding the failed
candidate-overlay regression. **The regression gate is NOT CLEARED.** Frozen place
semantics were not modified, the failed task was not replaced, and the candidate
was not merged, promoted or released. The existing release-confirmation proposal
and approval boundary remain separate from the T08 isolated development work.

## Evidence identity, replay and status

- Base image: `flexcell-t08:30fa2066`, sha256
  `97af41edcf2946ef453525fdae2ae3ab8a0754a113c1393932bfc4007a4e6fa0`.
- `provenance.json` inside each run records actual imported source paths/hashes.
  Candidate recorder summaries inherit the **image-base** revision tag; use the
  explicit overlay flag/file hashes for actual candidate identity, not that tag.
- `raw_runs.zip` holds **205 original files**, including failures, both regressions
  and source identity reports. Every member is checked against `raw_runs_sha256.json`.
- The unchanged existing recorder/evaluator produced the bundles/verdicts. Rest
  height comes from the TaskSpec; max_z comes from native trajectories. No gate
  or success threshold was adjusted after seeing outcomes.
- Five Gazebo sessions: control, acquisition failure, candidate retry, ordinary
  regression, original ordinary-task diagnostic. No model calls or hardware.

Read-only replay:

```sh
python3 setup/acceptance/evobot_safe_reposition_20261112/analyze_results.py
```

Current status: **Implemented + Unit Tested + Simulation Tested on one dev
instance; one full frozen task verdict PASS.** Formal T08 baseline remains
`CALIBRATION_UNSUPPORTED`; no Runtime-autonomous L4 acquisition is claimed.
Next: measure post-return state for bounded finishing, then preregister repeatability;
resolve the ordinary release regression before formal promotion or held-out claims.
