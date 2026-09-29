# ROADMAP — FlexCell long-term phases

> Living document. Milestone-based, no fixed dates — update when a phase moves.
> Execution detail lives in [DEVELOPMENT.md](DEVELOPMENT.md); the ratified Week-2 design of
> record is [WEEK2_PREPARATION.md](WEEK2_PREPARATION.md) (§0.5).

## Milestone map

| Milestone                              | Scope                                                                            | Status                                                       |
| -------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| **M1** Deterministic Workcell Baseline | Day 1-2 + Week 1 + Week 1.5                                                      | ✅ DONE (accepted; delivery baseline `7956d63`)              |
| **M2** Runtime Decision Foundation     | WorldState v2 → DecisionPolicy → FSMPolicy → replay harness → Jev (LLM deferred) | 🔵 CURRENT — umbrella over sub-milestones M2.1 / M2.2 / M2.3 |
| **M3** Hybrid Agent Benchmark          | Execute cells A-D on S1-S7; threshold sweep; calibration                         | ⚪ FUTURE — RFC #15                                          |

## Completed

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
| Benchmark harness + metrics report generator                               | #8                                                             | #15            |
| S7 perturbation scenario builder                                           | #9                                                             | #15            |
| JevPolicy + pluggable JevBackend (TypeSafe \| Local)                       | #10                                                            | #14            |
| LLMPolicy                                                                  | #11 — **DEFERRED (③)** until interface + runner + replay exist | #15            |
| HybridRouter + threshold sweep τ∈{0.5,0.7,0.9} + calibration report        | #12                                                            | #15            |
| ADR set from the ratified preparation                                      | #2                                                             | —              |

## Future

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
