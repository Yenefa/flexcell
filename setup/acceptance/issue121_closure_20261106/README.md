# Issue #121 closure window — 2026-11-06

Purpose: close the four review items raised against `7567791`, re-verify the **original
counterexample point** with a regrasp, and leave records that can be checked without the
author's machine.

## Environment

- Ubuntu 24.04, ROS 2 Jazzy, Gazebo Sim 8.15 headless (`gz sim -s`), isolated colcon install
  at `/home/ros/r4check` (merged view `/home/ros/r4merged/install` used only for the identity
  hashes, see the runner note below).
- Carry backend `detachable_joint`, MTC place path (`skill_backend: mtc`), decision policy `fsm`.
- Build: `colcon build --packages-select flexcell_skills flexcell_mtc --symlink-install` — 2 packages, 0 error.
- Tests: `colcon test --packages-select flexcell_mtc` → **14 tests, 0 failures**;
  `pytest test_sim_smoke_outcome.py test_release_attitude.py test_fourdof_reachability.py`
  → **20 passed**.

## Windows

| directory | case | command | result |
| --- | --- | --- | --- |
| `orig-point-regrasp/` | original #121 counterexample `(0.12, +0.04, 0.0175)` plus a regrasp to zone_2, 5.0 deg contract | `--case regrasp --place-pose 0.12 0.04 0.0175 --level-release-tolerance-deg 5.0` | `PASS`; task errors **0.0293 mm** and **0.1548 mm**; releases **0.1559° / 0.2157°**; horizontal drift **0.043 / 0.035 mm**; `place_error` **0.0681 / 0.6766 mm** |
| `gate-refusal-0p001/` | negative control, gate limit far below any achievable tilt | `--case gate_refusal --level-release-tolerance-deg 0.001` | `EXPECTED_FAILURE`; task `OUTCOME_FAILED`; `object_at_place: false`; place row `outcome=1 released=False`, detail `release tilt 0.085 deg exceeds 0.001 deg limit; carry held` |

Both windows are the same declared scene/profile as the earlier rounds; the only differences
are the goal pose and the gate limit.

## Why the gate limit is 0.001 deg, not 0.1 deg

With the full feasible phi interval enumerated, the achievable tilt at the staging point is
0.03–0.22 deg across runs. A 0.1 deg limit therefore sits *inside* the solution spread: one run
refused (0.143 deg) and another released (0.085 deg, gate detail `within 0.1 deg`). 0.001 deg is
below any physically meaningful tilt, so the control is deterministic.

## False-green regression (the review's first item)

The old harness let the ordinary success branch override the expected-failure branch: a
`gate_refusal` run whose place actually succeeded returned `PASS/0`. The decision now lives in
`sim_smoke.classify_outcome()` and `gate_refusal` can never return `PASS`; a success there is
`ROBOT_FAILURE` (the runner exits non-zero). Pinned by
`src/flexcell/flexcell_skills/test/test_sim_smoke_outcome.py`:

```
classify_outcome('gate_refusal', succeeded=True,  expected_failure=False) == 'ROBOT_FAILURE'
classify_outcome('gate_refusal', succeeded=True,  expected_failure=True)  == 'ROBOT_FAILURE'
classify_outcome('gate_refusal', succeeded=False, expected_failure=True)  == 'EXPECTED_FAILURE'
```

The review's live reproduction (gate 0.1 deg, place succeeded → `PASS/0`) is the first case in
that table; it was observed locally during this window before the limit was tightened.

## Reproducing

```
source /opt/ros/jazzy/setup.bash
source /home/ros/r4check/install/setup.bash
export PYTHONPATH=/home/ros/r4check/build/flexcell_skills:/opt/ros/jazzy/lib/python3.12/site-packages:$PYTHONPATH
export ROS_DOMAIN_ID=42 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
export FLEXCELL_REPO=<repo> FLEXCELL_INSTALL=/home/ros/r4merged/install
python3 scripts/sim_smoke.py --out <dir> --backend detachable_joint --skill-backend mtc \
    --case regrasp --place-pose 0.12 0.04 0.0175 --level-release-tolerance-deg 5.0
```

`FLEXCELL_INSTALL` must expose both `share/flexcell_skills/launch` and `lib/libflexcell*.so`;
with an isolated install those live under different prefixes, hence the merged view. Stop any
previous stack first and clear `/dev/shm/fastrtps_*` — stale DDS segments abort startup.

## Files

Each window keeps the raw records unedited: `result.json` (harness verdict, task outcomes,
timing), `params.yaml` (the exact profile, including both gate and solver tolerances),
`place.jsonl` / `pick.jsonl` / `verify.jsonl` (skill records with `object_before_release`,
`release_attitude`, `box_after`).
