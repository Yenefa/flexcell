# ROADMAP — FlexCell long-term phases

> Living document. Milestone-based, no fixed dates — update when a phase moves.

The [2026-10-27 trusted simulation plane](TRUSTED_SIMULATION_20261027.md) adds pinned
CPU reproduction, DetachableJoint oracle, MTC through the shared motion executor,
headless full-stack CI and an official LeRobot example. [ADR-004](ADR/ADR-004-trusted-simulation-plane.md)
authorizes these new profiles. Perception, hardware and M3/model qualification remain separate.
> Execution detail lives in [DEVELOPMENT.md](DEVELOPMENT.md); the ratified Week-2 design of
> record is [WEEK2_PREPARATION.md](WEEK2_PREPARATION.md) (§0.5).

Current source architecture and the evidence-gated development path are shown
in [the 2026-10-07 diagrams](ARCHITECTURE_AND_PLAN_20261007.md). This update
records implemented decision layers; it does not unfreeze n≥50 or declare M3
qualification complete.

## 顶层定位：Self-Evolving Agentic Robotics

本项目的研究对象不是"会抓放的机械臂"，而是 **Agent 如何开发、控制、验证并持续进化机器人**。
能力阶梯 **L1 开发 → L2 运行 → L3 进化**；**Agent 定 WHAT、执行器定 HOW、独立验证定 WHETHER**。
完整拆解（研究问题→可证伪命题→工作包→里程碑→指标）：[SELF_EVOLVING_AGENTIC_ROBOTICS.md](SELF_EVOLVING_AGENTIC_ROBOTICS.md)。

> 下方的里程碑是本定位下的**平台/基础设施**进展；平台通过 ≠ L1–L3 能力已达成。

## Milestone map

| Milestone                              | Scope                                                                            | Status                                                       |
| -------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **M1** Deterministic Workcell Baseline | Day 1-2 + Week 1 + Week 1.5                                                      | ✅ DONE (accepted; delivery baseline `7956d63`)              |
| **M2** Runtime Decision Foundation     | WorldState v2 → DecisionPolicy → FSMPolicy → replay harness → Jev / LLM / Hybrid | 🔵 CURRENT — source implemented; qualification incomplete |
| **M3** Hybrid Agent Benchmark          | Execute cells A-D on S1-S7; threshold sweep; calibration                         | ⚪ FUTURE — RFC #15                                          |

## Completed
## IYAIC 2026 competition

Registration 2026-11-13, contest 2026-11-21–22 (Henan, creative group). Packaging and a three-state
delivery index (implemented / accepted / branch-pending) live in
[competition/iyaic-2026/DELIVERY_STATUS.md](../competition/iyaic-2026/DELIVERY_STATUS.md). The
competition adds no milestone and does not unfreeze n>=50; TransferBench stays a branch-pending
capability to be split for review, not merged whole.

### Near-term goal (2026-11): IYAIC 2026 Henan creative group

Ship flexcell as an entry to the *AI & Robotics Innovation (Creative Group)*:
registration and materials due **2026-11-13**, division selection
**2026-11-21/22**. Goal, milestones and deliverables:
[competition/iyaic-2026/GOAL.md](../competition/iyaic-2026/GOAL.md) and
[SUBMISSION/](../competition/iyaic-2026/SUBMISSION/).


- **Day 1** — Gazebo Harmonic 8.15.0 + MoveIt 2 Plan & Execute on OpenMANIPULATOR-X
  (ROS 2 Jazzy), verified on-machine. See [DAY1_REPORT.md](../DAY1_REPORT.md).
- **Day 2** — Agent-callable MoveToPose skill (typed action → MoveIt → Gazebo → measured
  result). See [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md).
- **Week 1** — Deterministic skills (observe / pick / place / verify) + FSM;
  measured-not-inherited verification; ground-truth error 4.9-6.5 mm across runs.
- **Week 1.5** — Deterministic Demo Hardening: lifecycle CLI (start/stop/reset/status/health),
  strict health gate (17 checks), dual-object A/B scenario, bounded recovery (budget=1) +
  fixed failure injection (`/flexcell/inject`), 5/5 repeatability 2.5-10.6 mm. Delivery ACCEPTED.
- **Week-2 preparation** — architecture recon, DecisionPolicy design (4 implementations +
  deterministic safety gate), WorldState v2 freeze candidate, benchmark design (A-D × S1-S7 ×
  7 metrics + policy-input replay), Jev feasibility. **RATIFIED by chief review 2026-09-26**
  (six decisions, §0.5).

## Current — M2 Runtime Decision Foundation

Ratified implementation order: **WorldState → Decision Interface → FSMPolicy → Scenario
Replay → Jev → LLM**. Work is tracked in sub-milestones (implementation) plus RFC issues
(architecture of record):

| Step                                                                       | Implementation issues                                          | RFC / contract |
| -------------------------------------------------------------------------- | -------------------------------------------------------------- | -------------- |
| WorldState v2 freeze + versioned canonical serializer                      | #3                                                             | #16            |
| DecisionPolicy interface + Decision/TaskGoal/Constraints/TaskHistory types | #4                                                             | #14 (+#1)      |
| FSMPolicy + executor seam (default=fsm) + trace-shape parity               | #5                                                             | #14            |
| Deterministic safety gate + invalid-decision accounting                    | #6                                                             | #14            |
| Scenario runner + episode record + policy-input replay store               | #7                                                             | #15            |
| Benchmark harness + metrics report generator                               | #8 — implemented; batch qualification and pinned model replay pending | #15            |
| S7 perturbation scenario builder                                           | #9                                                             | #15            |
| JevPolicy + pluggable JevBackend (TypeSafe \| Local)                       | #10                                                            | #14            |
| LLMPolicy                                                                  | #11 — implemented; official-backend evidence in E-013/E-021 | #15            |
| HybridRouter + supported-bin threshold sweep + calibration report         | #12 — implemented; Q8 pilot τ=0.03/0.85, acceptance incomplete | #15            |
| ADR set from the ratified preparation                                      | #2                                                             | —              |

## Future

The current M3 claim is a cost hypothesis with independent task outcomes and a
zero-API-cost FSM control, not an established smarter policy. The Q8 pilot uses
the two supported-bin regimes tau=0.03/0.85; the historical 0.5/0.7/0.9 grid does
not distinguish the current calibrated bins. Narrower bins and policy superiority
are unqualified. S7 placement perturbation alone is not a differentiation oracle.
The truncated pilots leave n>=50 frozen. See [Q8 pilot](Q8_PILOT_20261005.md).

Immediate sequence: land the [batch provenance repair](HYBRID_BATCH_GATE_20261007.md),
diagnose the cross-arm grasp failure, then complete pinned model replay and a
new-fingerprint online smoke/acceptance battery. Review M3 entry under ADR-003,
pre-register differentiated S1-S7 cells and interleaved arm order, and retain
the sample freeze until evidence and human review permit a larger campaign.
Each arm keeps its own stable fingerprint under shared physics/verifier conditions.

- **M3 Hybrid Agent Benchmark** — cells A-D on S1-S7 (S7 perturbation track kept in
  primary, ⑥); pass/fail gates in #15. Gate rule: FSM ≥ every other cell on task success
  before any policy enters the critical path.
- **Real Robot Backend** — replace the simulation manipulation backend (see
  [ADR/ADR-001-simulation-manipulation-backend.md](ADR/ADR-001-simulation-manipulation-backend.md))
  with a real gripper backend; implementation-only swap, skill contracts unchanged.
- **Vision Integration** — replace the `SIMULATION_GROUND_TRUTH` source with camera-based
  observation; WorldState already isolates the source tag for exactly this swap.
- **NVIDIA Development Plane sandbox (parallel backlog)** — standalone Isaac ROS Agent
  Skills sandbox, Docker-isolated; only when a measured bottleneck justifies it.
- **Hardening backlog** — #13 (carry servo observability; touches the frozen carry backend,
  needs explicit go); contact grasping (replaces ADR-001 mechanism); carry chain-break
  detection.

## Research north star (chief's framing)

The core variable is no longer "how accurately it grasps" but "how to choose the correct
action under uncertainty" — Agentic Robotics.

## Route re-evaluation triggers (2026-09-28, from the M2.3 audit §5)

The stack bets are LTS-frozen to 2029 and the 2026-09-28 audit's external scan is
current — a calendar-based re-survey adds nothing. Re-evaluation is **trigger-based**
instead; at each trigger the relevant literature/landscape pass is redone and the
conclusion lands in an ADR or ROADMAP update:

| #   | Trigger                                                                                                                            | Re-evaluate                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| --- | ---------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T1  | **Before M3 starts** (M2 definition-of-done met)                                                                                   | Orchestration substrate (FSM vs MTC as treatment arm) — fresh literature pass, ADR-003 ratified (draft exists)                                                                                                                                                                                                                                                                                                                                                                                                              |
| T2  | **Lyrical migration window** (Jazzy EOL 2029-05 approaching, or a required feature is Lyrical-only)                                | Full stack re-selection (ROS 2 / Gazebo / MoveIt)                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| T3  | **Real-hardware decision point** (D4 exit condition fires, or hardware bring-up is scheduled)                                      | Sim-to-real + contact-grasping literature; contact grasp mechanism choice                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| T4  | **Before implementing #11 LLMPolicy**                                                                                              | VLA / LLM-planning landscape (the fastest-moving input; the deferred item is where staleness bites hardest)                                                                                                                                                                                                                                                                                                                                                                                                                 |
| T5  | **Before any vendor number becomes load-bearing** (e.g. Jev vendor's ~200× / 1-400 cost claims, p95 UNKNOWN per WEEK2_PREPARATION) | Independent reproduction before trusting                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| T6  | **Before any M3 cell number is quoted** (added 2026-09-29)                                                                         | Two measurement-integrity preconditions: (a) the `gate_flood` zero-traceback gate must actually be green — it has never been, the committed delivery-host reset artifacts carry the same ~1000-count `gz.msgs.Pose` flood, so the M2.3 "pb2 fix in place" claim is unsupported; (b) `flexcell_admin.py reset` must restore the canonical world after an abort-while-carrying (it reports `scene_cleared: false` + `DRIFT`), otherwise per-episode cell independence is not established and long batches confound each other |

T4 and the defect descriptions in T6 above record the 2026-09-28/29 review
context, rather than present host health. LLMPolicy subsequently shipped;
pose-worker/reset repairs and their qualified runs are recorded in E-020.
The underlying gates still apply: clean reset exits, canonical state and
flood-free acceptance must be proven for the deployment being measured.
