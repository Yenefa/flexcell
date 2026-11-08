# TransferBench split plan — 2026-11-08

> Branch `feat/transferbench-foundation-20261006`; merge-base `ffde775`; compared with current `main` `847785e`:
> **29 ahead / 211 behind / 1884 changed files** (the GitHub compare API truncates its file list at 300).
> **Cannot be merged whole.** This document is a review plan; it changes no runtime and claims no acceptance.

## Inventory

| Area | Files | Notes |
| --- | --- | --- |
| `setup/acceptance/*` evidence | 1805 | immutable measured records; identity must be preserved |
| `setup/transferbench/*`, `setup/12x_*.py`, `102_mainline_runtime.sh`, `cyclone_wsl_local.xml` | 40 | probes / harness / bench tooling |
| `src/` | 27 | interfaces, composite contracts, server integration, tests |
| `docs/` | 10 | design and qualification docs |
| root | 2 | `README.md`, `.github/workflows/ci.yml` |

## Reviewable units (proposed)

### U1 — composite interfaces (contract only)
`src/flexcell/flexcell_interfaces/{action/RunComposite.action, msg/CompositeStage.msg, msg/ObjectPosition.msg, CMakeLists.txt}`.
Impact: interface contract only, no behavior. Acceptance: colcon build of interfaces, rosidl shape check.

### U2 — composite contracts (pure Python)
`contracts/{composite,composite_checkpoint,composite_prepare,backend_health,receipt_json,goal_response,episode}.py` +
`test_composite*.py`, `test_backend_health.py`, `test_goal_response.py`.
Impact: pure modules; offline pytest. Dependency: U1 optional.

### U3 — composite execution integration (runtime)
`task_fsm_server.py`, `observe_server.py`, `place_server.py`, `move_to_pose_server.py`, `w1_client.py`,
`package.xml`, `test_executor_integration.py`, `test_place_dependency.py`, `test_controller_transport.py`.
Impact: real runtime behavior. Acceptance: offline colcon test **plus** a ROS/Gazebo window and a **new fingerprint**.
Risk: main changed all four servers since the base; expect conflicts.

### U4 — TransferBench harness (tooling)
`setup/transferbench/*` (runner / pilot / adjudicate / diagnostics / qualification), `setup/122..136_*.py`,
`102_mainline_runtime.sh`, `cyclone_wsl_local.xml`, `.github/workflows/ci.yml`.
Impact: tooling only; acceptance: offline selftests; the CI change is reviewed separately.

### U5 — bounded runner + hybrid guard (capability)
Subset: `bounded_runner.py`, `bounded_live.py`, `bounded_pose.py`, `bounded_hybrid_guard.py`, their tests,
`docs/BOUNDED_RUNNER.md`, `docs/BOUNDED_HYBRID_GUARD.md`. Dependency: U4.

### U6 — acceptance evidence (1805 files)
No runtime. Large. Decide between a separate evidence PR and a frozen external pointer; never rewrite or delete.

### U0 — documentation (land last, or with explicit pointers)
`docs/TRANSFER_BENCHMARK.md`, `COMPOSITE_TASKS.md`, `PRE_BATCH_CHECKPOINT.md`, `QUALIFICATION_*.md`,
`DIRECT_GRASP_DIAGNOSTIC.md`, and the edits to `README.md` / `ROADMAP.md` / `EXPERIMENTS.md`.

## Progress (2026-11-08)

| Unit | State | Note |
| --- | --- | --- |
| U1 interfaces | **MERGED** | PR #134 -> `c04863c`; `RunComposite.action`, `CompositeStage.msg`, `ObjectPosition.msg`; `ci` + `trusted-simulation` green |
| U2 pure contracts | **MERGED** | same PR; 6 pure modules + 5 offline test files (92 tests locally) |
| U4 harness | **BLOCKED on U6** | trial import gave 183 pass / **17 fail**, all reading `setup/acceptance/*` evidence; tooling and evidence must land together |
| U3 runtime | **MERGED** | PR #138 -> `7fecbe2`; live Gazebo composite chain OUTCOME_SUCCEEDED; plain smoke regression PASS; CI green |
| U5 bounded runner | not started | depends on U4 |
| U6 evidence (1805 files) | not started | separate decision: evidence PR vs frozen external pointer |
| U0 docs | partial | this plan + competition status only |

Excluded from U2 on purpose: `test_composite_resume_audit.py` (needs `setup/129_*`, i.e. U4).
Server-integration tests (`test_composite_server`, `test_place_dependency`, `test_controller_transport`) stay in U3.

## Recommended order
1. U1 -> U2 -> U3 (runtime chain, one unit per PR, CI + ROS/Gazebo, new fingerprint).
2. U4 -> U5 (tooling, can run in parallel with the runtime chain).
3. U0 docs after the code lands, so unmerged APIs are not documented as current.
4. U6 evidence per the evidence-identity policy.

## Rebase risk
`main` advanced 211 commits. Direct overlaps: `README.md`, `docs/ROADMAP.md`, `docs/EXPERIMENTS.md`,
`.github/workflows/ci.yml`, the four skill servers, `w1_client.py`, `test_executor_integration.py`,
`flexcell_interfaces/CMakeLists.txt`, `package.xml`. Every unit must be rebased and re-tested; conflicts
are expected in U3 and U0.

## Acceptance rules
- Runtime unit: offline suites **plus** ROS/Gazebo window; new fingerprint; cloud unit tests alone are not acceptance.
- Evidence: preserved as-is; never edited to make a new claim pass.
- n>=50 stays frozen; no AC@90 claim; no decision/skill/execution/verification boundary refactor.

## Decision needed (human)
Contest dates: registration 2026-11-13, division contest 2026-11-21–22. Options:
(a) land only U1/U2 (offline contracts) before the contest and defer U3 runtime;
(b) freeze TransferBench entirely for the contest and keep it branch-pending;
(c) if the demo needs composite tasks, schedule U1-U3 with a ROS/Gazebo window before 2026-11-13.
Recommendation: (b) for the contest scope (core workcell + visual pick), unless the showcase needs composite.