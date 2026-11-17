# Carry backend physical results (2026-11-16)

What a task actually does under each `carry_backend`, measured on one host with
the declared world and the repo's own harness. This page exists because a
`teleport` PASS looks identical to a physical PASS in a summary table, and it
must not be read as one.

## What the backends are

| `carry_backend` | how the object is held | evidence value |
| --- | --- | --- |
| `teleport` (default) | gz `set_pose` re-issued at 10 Hz at the offset frozen at engage | **declared simulation-only shortcut**; `carry_server` says "CarryState is backend state, never physical evidence" |
| `velocity_servo` | plugin `libflexcell_carry_dynamics.so` constrains pose **and** velocity every physics step; gravity stays on; release removes the constraint and the object free-falls | a physics-step constraint, not a force-closed grasp |
| `detachable_joint` | Gazebo `DetachableJoint` system plugin; a real parent/child joint | the only backend whose attachment is a physics joint; D3 is `NO_GO_FOR_DEFAULT_ADMISSION`, experimental oracle |

`skill_backend` is a second, independent axis: `legacy` (repo skill servers) vs
`mtc` (MoveIt Task Constructor planning). All runs below are `legacy`.

## Environment

WSL2 Ubuntu 24.04, ROS 2 Jazzy, Gazebo vendor build, 12 cores. Built with the CI
layout, which is what makes `infra/runtime_identity.py` pass:

```bash
colcon build --base-paths src/flexcell --merge-install --symlink-install \
  --install-base install_merged --packages-up-to flexcell_skills
colcon build --base-paths src/flexcell --merge-install --symlink-install \
  --install-base install_merged --build-base build_merged \
  --packages-select flexcell_gazebo flexcell_mtc     # native plugins for contact trace
export FLEXCELL_REPO=$PWD FLEXCELL_WS=$PWD FLEXCELL_INSTALL=$PWD/install_merged
```

Each run is one bounded task, one attempt, no replacement, no model calls.

## Results

| run | backend | world | outcome | final position error |
| --- | --- | --- | --- | --- |
| PHYS-1 | `velocity_servo` | `f78a469d…` | **PASS** `PICK_A:OK / PLACE_A:OK / VERIFY_A:OK` | **4.07 mm** |
| PHYS-2 | `velocity_servo` | `f78a469d…` | **PASS** (same trace) | **12.26 mm** |
| PHYS-3 | `velocity_servo` | same | **PASS** (same trace) | **2.19 mm** |
| PHYS-4 | `velocity_servo` | same | **PASS** (same trace) | **6.86 mm** |
| PHYS-5 | `velocity_servo` | same | **PASS** (same trace) | **9.87 mm** |
| CONTROL-2 | `teleport` | `422f5a6a…` | PASS - reference only, not physical evidence | 9.20 mm |
| PHYS-DJ2 | `detachable_joint` + `--contact-trace --physics-step-s 0.002` | `82e74a45…` | `PICK_A:OK`, **`PLACE_A:FAIL`** | - |
| PHYS-DJ3 | same as DJ2 (reproduction) | `82e74a45…` | identical: `PICK_A:OK`, `PLACE_A:FAIL` | - |

All five `velocity_servo` run directories are archived under
`setup/acceptance/pick_place_repetition_20261116/`, with per-file sha256 in its
`results.json`. Before that archive existed only the first two numbers appeared
anywhere, so `n = 5` was not checkable; it is now. Each run archived there also
records that `contact_force_observed` was false in every physics row, which is
the reason a PASS here says nothing about grip force.

### Engine-level evidence (not agent reports)

- `velocity_servo` runs stepped the physics loop 10,940 and 11,124 steps
  (20 ms trace windows, 5 ms internal steps) over 54.7 s and 55.6 s of simulated
  time. The object rose 0.115 m / 0.107 m and returned to z = 0.0175 m.
- `contact_force_observed` is **false in every row** of both
  `velocity_servo` runs, and `joint_component` is false: this task chain does
  not measure contact forces, so a PASS here says nothing about grip force or
  friction.
- `detachable_joint` runs recorded a real attachment:
  `joint_component = true` in **481 of 1,516** physics rows, and the pick row
  states "picked target_box_a: attached, measured rise **0.123 m**".
- The same runs recorded `contact_steps.jsonl` from the physics engine
  (`ECM_POST_PHYSICS`, 2 ms, 21,489 rows): `ground_plane ↔ target_box_b` in
  every row, `ground_plane ↔ target_box_a` in **17,241** rows - i.e. the box
  left the ground for about **8.5 s** of the 43 s run.
- **`PLACE_A` fails with an already-documented condition, not a new one**:
  `gripper did not open (position=-0.011 requested=0.02 stalled=True)`
  (`ERR_PLACE_FAILED`, legacy code 25). This is the known gripper-aperture
  defect recorded in `docs/MISSION_UPDATE_20261112_R5.md` §19.2 and
  `setup/acceptance/evobot_gripper_false_negative_measured_20261112/`:
  `place` judges release by aperture with a 0.005 m tolerance while a free-space
  open only reaches 0.0104 m, so the aperture error is ~0.0096 m and only
  `reached_goal` saves the check. It reproduces deterministically here.

**Why `velocity_servo` PASSes while `detachable_joint` does not is a hypothesis, not
a finding.** The two backends take different place paths
(`place_server.py`: `joint_targets = carry_backend == 'detachable_joint'`), and a
physics joint holding the box against the fingers is a plausible reason the
fingers cannot open - but no finger force, joint force or aperture trace was
collected, so this page does not claim a cause.

## What this establishes

1. A **physical-backend** task (default `velocity_servo`, declared world) completes
   end to end and passes the independent verifier on five repeated runs: 5/5,
   errors 2.19-12.26 mm against a 60 mm tolerance. The five run directories are
   archived, so this is checkable rather than quoted.
2. The `detachable_joint` backend really attaches and lifts (engine-side joint
   rows plus ECM contact gaps), then `PLACE_A` fails deterministically on the
   **already-known gripper-aperture defect** documented in R5 §19.2. This run is
   another instance of that defect at task level, not evidence that the
   detachable backend is uniquely broken.
3. `teleport` PASS must not be quoted as physical evidence, and the physics
   trace alone cannot distinguish it from `velocity_servo`; the discriminator is
   the backend parameter and the plugin, not the pose series.

## What this does NOT establish

- No contact-force or friction claim: `contact_force_observed` was never true in
  the carry runs.
- No capability or statistics claim: n = 5 `velocity_servo` repetitions
  (archived under `setup/acceptance/pick_place_repetition_20261116/`), single host,
  `qualification: FUNCTIONAL_SMOKE_ONLY`, and `detachable_joint` is explicitly
  not admitted as the default backend.
- Nothing about #237's scheduling stall; that is covered separately in
  `FULL_CONFIG_SCHEDULING_20261116.md`.

## Reproduce

```bash
# physical (default) backend
python3 scripts/sim_smoke.py --out /tmp/phys --backend velocity_servo --skill-backend legacy

# attachment backend with engine contact trace (needs the native plugins built)
python3 scripts/sim_smoke.py --out /tmp/dj --backend detachable_joint \
  --skill-backend legacy --contact-trace --physics-step-s 0.002
```


## Decision unchanged: `detachable_joint` stays NO_GO for default admission

Nothing in this round changes `docs/DETACHABLE_ADMISSION_20261027.md`. The
decision there is `NO_GO_FOR_DEFAULT_ADMISSION`, and the runs above do not meet
any of its six #57 criteria: no five-cycle attach/detach qualification, no
ten-second SE(3) stability, no fitted free-fall trace, no 500 Hz step (this world
runs 2 ms, not 2 ms of a 500 Hz *declared* profile with contact forces), no
complete legacy parity matrix, and no integrated contact-state attach case.

Two conditions before anyone reopens that decision:

1. **Release path** - `PLACE_A` fails on the documented gripper-aperture defect
   (issue #255). It has to be fixed and re-run, not worked around by dropping the
   check or relaxing the tolerance.
2. **Force measurement** - finger force and joint force are not measured at all
   today. `contact_force_observed` was false in every carry run, so no statement
   about grip force, friction or slip can be made from these runs. A real
   attachment qualification needs those channels, plus the SE(3) and free-fall
   traces #57 already asks for.

## Next step for a stronger physical conclusion

Pick/place is the wrong chain for contact evidence: the carry is a backend
constraint, so the interesting physics never shows up as contact. The push chain
is where contact is measured, and it is exercised through
`src/flexcell/flexcell_skills/run_contact_push.py <task.json> <out>` against one
declared push objective from `benchmark/tasks/t08_*/T08-push-*.json`.

What that requires (identified, **not yet executed** in this round):

| requirement | where it comes from |
| --- | --- |
| world with `libflexcell_physics_trace.so` + `libflexcell_contact_trace.so` | `scripts/sim_profile.py` with `contact_trace=True`, which also forces `backend=detachable_joint` and `physics_step_s=0.002` |
| trace destinations | env vars read by the native plugins: `FLEXCELL_PHYSICS_STEP_LOG`, `FLEXCELL_CONTACT_STEP_LOG` (see `PhysicsTrace.cc:65`, `ContactTrace.cc:62`; `scripts/contact_probe.py` sets the contact one) |
| a model directory containing `robot.urdf` | `run_contact_push.py --model` expects `<dir>/robot.urdf` for `ContactGeometry`; CI ships it at `/artifacts/model`, and it is **not** in this repository, so it has to be generated from `open_manipulator_description` before the push adapter can run |
| a running task-scoped stack | pass one push task at a time; the historical acceptance used a task-scoped graph, not the full default graph |

These prerequisites were resolved in this session and five declared push attempts
were run; three reached the goal with measured engine contact. See
`docs/diagnosis/PUSH_CHAIN_CONTACT_20261116.md` for the numbers and for the two
attempts that failed before dispatching any motion.
