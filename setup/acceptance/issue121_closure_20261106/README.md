# Issue #121 closure window — 2026-11-06

Purpose: close the review items raised against `7567791` and `a86fc5d`, re-verify the **original
counterexample point** with a regrasp, and leave records that can be checked without the author's
machine.

## Environment

- Ubuntu 24.04, ROS 2 Jazzy, Gazebo Sim 8.15 headless (`gz sim -s`), isolated colcon install under
  `/home/ros/r4check` (a symlink-only merged view `/home/ros/r4merged/install` is used so the
  identity tool can hash `share/` and `lib/` from one prefix — see `provenance.md`).
- Carry backend `detachable_joint`, MTC place path (`skill_backend: mtc`), decision policy `fsm`.
- Build: `colcon build --packages-select flexcell_skills flexcell_mtc --symlink-install` — 2 packages, 0 error.
- Tests: `colcon test --packages-select flexcell_mtc` → **14 tests, 0 failures**;
  `pytest test_sim_smoke_outcome.py test_release_attitude.py test_fourdof_reachability.py`
  → **20 passed**.

## Windows

| directory | case | command | result |
| --- | --- | --- | --- |
| `orig-point-regrasp/` | original #121 counterexample `(0.12, +0.04, 0.0175)` plus a regrasp to zone_2, 5.0 deg contract | `--case regrasp --place-pose 0.12 0.04 0.0175 --level-release-tolerance-deg 5.0` | `PASS`; task errors **0.0293 mm** and **0.2926 mm**; releases **0.1559° / 0.2157°**; horizontal drift **0.043 / 0.035 mm**; `place_error` **0.0681 / 0.6766 mm** |
| `gate-refusal-0p001/` | negative control, gate limit far below the tilt actually achieved in this run | `--case gate_refusal --level-release-tolerance-deg 0.001` | `EXPECTED_FAILURE`; task `OUTCOME_FAILED`; `object_at_place: false`; place row `outcome=1 released=False`, detail `release tilt 0.085 deg exceeds 0.001 deg limit; carry held` |

Both windows use the same declared scene/profile as the earlier rounds; the only differences are
the goal pose and the gate limit. Provenance is in `provenance.md`; each window keeps its own
`identity.stdout`. Two digests are in play and must not be conflated: the source claim rests on the
**git-tracked** digest `e91eda9b…` (255 files), while the harness recorded the working-tree walk
`3b41f5a1…` (261 files) which also contains six local `.pytest_cache` files.

## Why the gate limit is 0.001 deg, not 0.1 deg

With the full feasible phi interval enumerated, the tilt actually achieved at the staging point
varied across runs in the range **0.03–0.22 deg**. A 0.1 deg limit therefore sat *inside* that
spread: one run refused (0.143 deg) and another released (0.085 deg, gate detail `within 0.1 deg`).
0.001 deg is below any physically meaningful tilt for this fixture, so the control exercises the
refusal path instead of sampling the solver's output.

**Boundary:** this is a single-run observation. It does not establish a universal physical lower
bound for box tilt, nor that a 0.001 deg limit will refuse on every future run — a release with a
tilt below 0.001 deg would legitimately pass. The general statement the code supports is only:
*when* the measured tilt exceeds the declared limit, the release is refused and the carry held.

## False-green regression (the review's first item)

The old harness let the ordinary success branch override the expected-failure branch: a
`gate_refusal` run whose place actually succeeded returned `PASS/0`. The decision now lives in
`sim_smoke.classify_outcome()` and `gate_refusal` can never return `PASS`; a success there is
`ROBOT_FAILURE` and the runner exits non-zero. Pinned by
`src/flexcell/flexcell_skills/test/test_sim_smoke_outcome.py`:

```
classify_outcome('gate_refusal', succeeded=True,  expected_failure=False) == 'ROBOT_FAILURE'
classify_outcome('gate_refusal', succeeded=True,  expected_failure=True)  == 'ROBOT_FAILURE'
classify_outcome('gate_refusal', succeeded=False, expected_failure=True)  == 'EXPECTED_FAILURE'
```

The review reproduced the original defect through the real runner **using simulated commands**
(not a live simulation). Locally, one live run at a 0.1 deg limit did place successfully
(release tilt 0.085 deg) and the new classifier returned `ROBOT_FAILURE`; that run's records were
deleted and are registered below.

## Missing records register

| run | why missing | what is lost | what remains |
| --- | --- | --- | --- |
| `/home/ros/live121-gate2/run-43f66e538650` (2026-11-06 ~05:09 UTC, `gate_refusal`, limit 0.1 deg) | directory removed by the runner's `rm -rf` before the retry | result.json, place.jsonl, params.yaml, identity.stdout | the observed behaviour (place succeeded, `release tilt 0.087 deg within 0.1 deg`, classifier `ROBOT_FAILURE`) is **not** independently verifiable from committed files; only the unit test pins the branch |

No other window on this branch was deleted.

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

Stop any previous stack first and clear `/dev/shm/fastrtps_*` — stale DDS segments abort startup
with a JSON decode error at the health check. Wall-clock timings depend on machine load; the
solver output at this target is not asserted to be reproducible to the digit.

## Files

Each window keeps the raw records unedited: `result.json` (harness verdict, task outcomes,
timing), `params.yaml` (the exact profile, including both gate and solver tolerances),
`identity.stdout` (the source/artifact digests the run was executed with), and
`place.jsonl` / `pick.jsonl` / `verify.jsonl` (skill records with `object_before_release`,
`release_attitude`, `box_after`).
