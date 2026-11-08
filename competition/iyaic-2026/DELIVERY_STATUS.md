# IYAIC 2026 delivery status

> Status index, not a new acceptance. Evidence entries live in [docs/EXPERIMENTS.md](../../docs/EXPERIMENTS.md)
> and `setup/acceptance/`. Snapshot: `main` = `8a16a35`, 2026-11-08.
> Three states are used exactly: **Implemented** (source merged, CI/offline covered),
> **Accepted** (has a frozen/measured acceptance record), **Branch pending review** (not merged).

## 1. Accepted (frozen baseline or measured acceptance)

| Capability | Evidence |
| --- | --- |
| Deterministic workcell baseline (Day1/2, Week1, Week1.5) | `setup/acceptance/{day1,day2,week1,week15}`; frozen behavior baseline `7956d63` |
| Trusted simulation plane gates (native five cycles, joint follow, false attach, sim smoke) | CI `trusted-simulation` jobs on `8a16a35` (public repo, push) |
| Camera data plane: LeRobot writer + official loader roundtrip | `camera-data` job green on `main` (n=3); reconcile backfill for sporadic live-frame loss |
| Visual pick + region clear/restore (functional, single-window) | #114 n=1 demo (2026-11-04), #119 closed, #126 plan tool |

## 2. Implemented (on main, CI/offline covered; not a fresh physical acceptance)

| Capability | Where |
| --- | --- |
| WorldState v2, canonical serializer, DecisionPolicy/FSMPolicy, recovery seam | `src/flexcell/flexcell_skills/` |
| MTC execution, carry backends (teleport / velocity_servo / detachable_joint) | `flexcell_mtc`, `flexcell_gazebo` |
| Camera bridge (#116), AprilTag read-only localization (#118), occlusion/first-frame fix (#120) | merged, `docs/ROS_MCP.md` |
| Release attitude / level-release geometry + gate-refusal controls (#121, #122, #123) | merged `8a16a35`; offline + CI tests |
| Recorder rosbag reconcile + LineWriter (#128, #130) | merged; `camera-data` green |
| Harness/tooling honesty gates (#28, #29) | merged |

> "Implemented" means the source is on `main` and the offline/CI suites pass. It is **not** a claim
> of a fresh ROS/Gazebo physical acceptance for every path, and still less a success-rate claim.

## 3. Branch pending review (not merged)

| Branch | State vs main | Plan |
| --- | --- | --- |
| `feat/transferbench-foundation-20261006` (TransferBench) | diverged: **ahead 29 / behind 211 / 300 files** | **Do not blind-merge.** Split into reviewable capabilities (combined multi-task, pause/resume), re-base onto current `main`, and re-accept each with a new fingerprint. |

## Boundaries
- n>=50 stays frozen; M3/hybrid qualification is not claimed here.
- Competition dates: registration 2026-11-13, contest 2026-11-21–22.
