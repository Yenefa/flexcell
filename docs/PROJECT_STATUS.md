# EvoBot — Project Status

**As of:** 2026-11-11 00:25 (+08:00)  
**Branch:** `autonomous/flexcell-remediation` (52+ commits, pushed, **unmerged**)

## Where EvoBot actually stands

| Level | Name | Status |
| --- | --- | --- |
| 1 | Execute | **Baseline A only**, 1/144 instances, independently verified |
| 2 | Compose | Not started |
| 3 | Recover | Not started (under EvoBot; recovery exists in the FlexCell track) |
| 4 | Develop | Not started |
| 5 | Improve | Not started (under EvoBot) |
| 6 | Learn | Not started (P2 item ② failed in the FlexCell track) |
| 7 | Transfer | Not started |
| 8 | Generalise | Not started |

**Level 1 is claimed for Baseline A only.** No agent-planned task has been run yet.

## Component status (evidence ladder)

| Component | Designed | Implemented | Unit Tested | Sim Tested | Indep. Verified | Generalised |
| --- | --- | --- | --- | --- | --- | --- |
| TaskSpec schema | yes | yes | yes | — | — | — |
| Generator T01-T06 | yes | yes | yes | — | — | — |
| Generator T07-T10 | yes | **no** (refuses) | — | — | — | — |
| Independent evaluator | yes | yes | yes | yes | yes | — |
| Observation bridge | yes | yes | yes | yes | yes | — |
| Baseline A executor | yes | yes | yes | **1 instance** | **1 instance** | no |
| RunComposite client | yes | yes | — | yes | — | — |
| Baseline B (runtime agent) | yes | **no** | — | — | — | — |
| Baseline C (self-evolving) | yes | yes (skeleton) | **yes (75 tests)** | no | no | no |
| Experience store | yes | yes | **yes** | — | — | — |

## What was proven today

`T01-train-seed1000` executed on the real Gazebo stack and passed the independent
evaluator: placement errors 9.26 mm and 4.39 mm against a 60 mm tolerance, both
objects resting, `false_success=false`. Evidence:
`setup/acceptance/evobot_t01_baseline_a_20261111/`.

The plan was derived **mechanically**, not by an agent. This is Baseline A by design:
it measures the stack, so that a later agent advantage can be attributed to the agent.

## What was NOT proven

- ~~No agent has planned a task yet. Baselines B and C do not exist as code.~~
  **CORRECTED 2026-11-11.** This was wrong when written. Baseline B v1 already existed and had
  been committed 91 minutes earlier as `9c59d5b2`, with a verified Gazebo run
  (`evobot_t01_baseline_b_20261111/`: PASS, 10.34 / 5.55 mm). A document edited after a commit
  must not claim the commit did not happen. Now: **B v1 exists (superseded)**; **B v2 exists and
  is Unit Tested + plan-level only** (`setup/acceptance/evobot_baseline_b_v2_20261111/`,
  17/18 planned, 17/17 plan-level correct, all credentials through the gate). No B result has
  been graded by the independent evaluator on a new task yet, so the *usable* claim about B is
  still exactly "a plan, not a success". C remains a skeleton.
- Baseline A v0: 6/6 on T01-T06 seed1000 (Wilson 95% CI 0.61-1.00, false_success 0),
  frozen in `setup/acceptance/evobot_baseline_a_v0_20261111/`; the 72-instance run
  (T01-T06 x 12 seeds) is in flight and no number from it is claimed yet.
- 1 of 144 instances at the time of writing. No generalisation, no held-out evaluation.
- ~~Held-out isolation is **specified but not enforced**~~ — **CLOSED 2026-11-11**.
  `scripts/heldout_isolation.py` locks `held_out/`, `evaluators/` **and `generators/`**
  to `root:ros 0750`; uid 1001 is denied, the evaluator still grades, and the mutation
  (chmod 755) makes the verifier exit 1. Evidence:
  `setup/acceptance/evobot_heldout_isolation_20261111/`. Rung: Independently Verified
  (mechanism only). Residual: a root process and WSL interop still bypass it — measured
  and disclosed, not hidden.
- T07-T10 cannot be emitted; the missing physical primitives are listed in
  `docs/TASK_CATALOG.md`.

## Defects found and fixed in this round

| # | Defect | Kind | Fix |
| --- | --- | --- | --- |
| 1 | Generator declared a third box the default world lacks | my error: asset ≠ scene | scene composition moved to `SCENES`; regression test added |
| 2 | T01 `unmoved` listed an object outside the scene | same root cause | drawn from scene; test asserts it |
| 3 | `error 41 another task owns the arm` | tooling | launch stack directly instead of via sim_smoke |
| 4 | No `RunComposite` client existed | tooling gap | wrote one |

## Next

1. **Baseline B**: an agent that plans from the instruction and the observation, using
   only existing skills. Same tasks, same evaluator.
2. **Enforce held-out isolation** before any generalisation claim.
3. Then Baseline C and the experience store.

## Outstanding human decisions

- Merge or open a PR (branch is pushed, unmerged).
- Enforce workspace isolation for held-out tasks (needs a decision on how the agent
  process is sandboxed).
- Physical safety chain still BLOCKED: no hardware, and nothing here has run on a real
  arm.

## 2026-11-11 增补（round 11）

- **首次真实泛化测量**：6 个 held-out、5 类模板，强制隔离下干净通过 5/6 = 83%，
  另有 1 例执行器/验收器分歧单列；False Success Rate 0.0%。
  见 `setup/acceptance/evobot_heldout_n6_20261111/`。
- **held-out 隔离已强制**：公开任务 / 封存答案（root:root 600）+ 隔离 UID。
- **Baseline C 骨架**：经验库、诊断、检索、回归门，75 个离线测试。
  **仍未在 Gazebo 上运行**，不宣称 Level 5/6。
- **三臂仍有缺口**：C 未配对执行，未证明经验迁移有效。
