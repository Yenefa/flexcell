# IYAIC 2026 delivery status

> Status index, not a new acceptance. Evidence entries live in [docs/EXPERIMENTS.md](../../docs/EXPERIMENTS.md)
> and `setup/acceptance/`. Snapshot: `main` = `49183b5`, 2026-11-09.
> Canonical status: [docs/PROJECT_STATUS.md](../../docs/PROJECT_STATUS.md); statistics: [docs/STATS_AUDIT.md](../../docs/STATS_AUDIT.md).
> Three states are used exactly: **Implemented** (source merged, CI/offline covered),
> **Accepted** (has a frozen/measured acceptance record), **Branch pending review** (not merged).

## 1. Accepted (frozen baseline or measured acceptance)

| Capability | Evidence |
| --- | --- |
| Deterministic workcell baseline (Day1/2, Week1, Week1.5) | `setup/acceptance/{day1,day2,week1,week15}`; frozen behavior baseline `7956d63` |
| Trusted simulation plane gates (native five cycles, joint follow, false attach, sim smoke) | CI `trusted-simulation` jobs on `8a16a35` (public repo, push) |
| Camera data plane: LeRobot writer + official loader roundtrip | `camera-data` job green on `main` (n=3); reconcile backfill for sporadic live-frame loss |
| Visual pick + region clear/restore (functional, single-window) | #114 n=1 demo (2026-11-04), #119 closed, #126 plan tool |

## 1b. Added 2026-11-09 (accepted)

| Capability | Evidence |
| --- | --- |
| Self-improvement loop (real Gazebo, W5-E2b/E2d) | `runs/p1.5-w5e2b-20261109/` 3/3, `runs/p1.5-w5e2d-20261109/` 2/2; offline demo `experiments/pilot-001/demo/replay.py` |
| Substrate comparison C3–C11 (FSM vs MTC) | `setup/acceptance/c3..c11_*`; C11 retry evaluation 12/12 PASS |

## 2. Implemented (on main, CI/offline covered; not a fresh physical acceptance)

| Capability | Where |
| --- | --- |
| WorldState v2, canonical serializer, DecisionPolicy/FSMPolicy, recovery seam | `src/flexcell/flexcell_skills/` |
| MTC execution, carry backends (teleport / velocity_servo / detachable_joint) | `flexcell_mtc`, `flexcell_gazebo` |
| Camera bridge (#116), AprilTag read-only localization (#118), occlusion/first-frame fix (#120) | merged, `docs/ROS_MCP.md` |
| Release attitude / level-release geometry + gate-refusal controls (#121, #122, #123) | merged `8a16a35`; offline + CI tests |
| Recorder rosbag reconcile + LineWriter (#128, #130) | merged; `camera-data` green |
| Harness/tooling honesty gates (#28, #29) | merged |
| TransferBench U1/U2: composite interfaces + pure contracts (#134, `c04863c`) | merged; offline + CI green |
| TransferBench U3: composite runtime integration (#138, `7fecbe2`) | merged; live Gazebo chain succeeded, plain smoke regression PASS, CI green |

> "Implemented" means the source is on `main` and the offline/CI suites pass. It is **not** a claim
> of a fresh ROS/Gazebo physical acceptance for every path, and still less a success-rate claim.

## 3. Branch pending review (not merged)

| Branch | State vs main | Plan |
| --- | --- | --- |
| `feat/transferbench-foundation-20261006` (TransferBench) | diverged: **ahead 29 / behind 211 / 1884 files** (1805 are acceptance evidence) | **Do not blind-merge.** Split into reviewable units U1-U6; see [TRANSFERBENCH_SPLIT_PLAN_20261108.md](../../docs/TRANSFERBENCH_SPLIT_PLAN_20261108.md). |

## Local acceptance capability

The delivery desktop runs the ROS/Gazebo acceptance **natively in WSL** (Mesa llvmpipe, no
Docker, no GPU passthrough): plain smoke PASS at 0.514 mm and camera smoke PASS at 10.85 mm,
with the rosbag reconcile backfilling 146 camera frames under the slower software renderer.
Provenance caveat: the upstream ROBOTIS checkout is `6c563fd`, not the pinned `17efe42`, so a
locked re-run is still required. Details: [LOCAL_SIM_ACCEPTANCE_20261108.md](../../docs/LOCAL_SIM_ACCEPTANCE_20261108.md).

## Boundaries
- n>=50 stays frozen; M3/hybrid qualification is not claimed here.
- Competition dates: registration 2026-11-13, contest 2026-11-21–22.
