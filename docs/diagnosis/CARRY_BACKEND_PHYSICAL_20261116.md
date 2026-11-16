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
| CONTROL-2 | `teleport` | `422f5a6a…` | PASS - reference only, not physical evidence | 9.20 mm |
| PHYS-DJ2 | `detachable_joint` + `--contact-trace --physics-step-s 0.002` | `82e74a45…` | `PICK_A:OK`, **`PLACE_A:FAIL`** | - |
| PHYS-DJ3 | same as DJ2 (reproduction) | `82e74a45…` | identical: `PICK_A:OK`, `PLACE_A:FAIL` | - |

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
- **The reproducible defect**: `PLACE_A` fails with
  `gripper did not open (position=-0.011 requested=0.02 stalled=True)`
  (`ERR_PLACE_FAILED`, legacy code 25). The box is held by a physics joint, so
  opening the gripper is a no-op and the place release never confirms. This
  reproduces twice.

## What this establishes

1. A **physical-backend** task (default `velocity_servo`, declared world) completes
   end to end and passes the independent verifier: 2/2, errors 4.07 mm and
   12.26 mm against a 60 mm tolerance.
2. The `detachable_joint` backend really attaches and lifts (engine-side joint
   rows plus ECM contact gaps), and its **release path is broken for pick/place**:
   `PLACE_A` fails deterministically because the gripper cannot open while the
   object is attached by a joint.
3. `teleport` PASS must not be quoted as physical evidence, and the physics
   trace alone cannot distinguish it from `velocity_servo`; the discriminator is
   the backend parameter and the plugin, not the pose series.

## What this does NOT establish

- No contact-force or friction claim: `contact_force_observed` was never true in
  the carry runs.
- No capability or statistics claim: n = 2 per backend, single host,
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
