# ARCHITECTURE — FlexCell system

> Implementation snapshot: main `a9b6a62`, reviewed 2026-10-17. Week-1.5 delivery
> `7956d63` remains the historical parity reference, not today's full architecture.
> Implementation and online qualification are separate. The ratified design lives in
> [WEEK2_PREPARATION.md](WEEK2_PREPARATION.md); decisions live in [ADR/](ADR/); the
> decision-layer RFC is #14.

## Layered view

    Runtime Decision Layer        ← implemented: FSM / Jev(Clef) / LLM / Hybrid
            |  Decision objects only
    Task Executor                 ← task_fsm_server.py: gate, dispatch, budget, episode
            |  typed skill actions
    Skill Server                  ← observe / pick / place / verify / carry / move_to_pose
            |  ROS 2 topics & actions
    ROS 2 Jazzy / MoveIt 2        ← planning, execution, ros2_control
            |
    Robot Backend                 ← today: Gazebo Harmonic 8.15 sim (ADR-001); real arm later

Models may only decide **task-level actions**; they never control joints, trajectories,
parameters, or safety. That separation is enforced by the deterministic gate (#6), not by
policy goodwill.

## Pipeline: historical reference and current implementation (ADR-002)

    HISTORICAL REFERENCE (Week-1.5, frozen):

        w1_client / admin
              │  /run_demo · /run_pick_place
              ▼
        task_fsm_server  (historical hard-coded FSM + bounded recovery)
              │  /observe · /pick_object · /place_object · /verify_object
              ▼
        Skills (observe · pick · place · verify · carry · move_to_pose)
              │
              ▼
        MoveIt 2 → ros2_control → Gazebo Harmonic (ADR-001 backend)

    CURRENT (M2 implementation; default=fsm retains the frozen policy grammar):

        Policy (FSM │ Jev │ LLM │ Hybrid)
              │  Decision objects — the only channel down
              ▼
        Executor  (safety gate · dispatch · budget accounting · evidence)
              │  typed skill actions
              ▼
        Skills → ROS  (verification stays policy-blind; executor checks postconditions)

Policy objects and the gate are modules inside TaskFsmServer, not separate ROS
services. Both `/run_demo` and `/run_pick_place` use `_execute_plan`, the policy
seam and EpisodeRecorder. The original missing-seam description in issue #22 is
superseded; remaining scenario/report qualification still needs reconciliation.
The batch report can supply an explicit S4 cell; generic `pick_place_v1` records
must not all be relabeled S4.

Boundary rules B1-B6 (typed channels, budget ceiling, gate-before-dispatch,
policy-blind verification, parity bar, replaceable parts) are frozen in
[ADR/ADR-002-runtime-decision-layer-boundary.md](ADR/ADR-002-runtime-decision-layer-boundary.md);
the line-anchored extraction map for `task_fsm_server.py` is its Appendix A.

## The three separated concerns

### Decision layer — WHAT to do next (models allowed here)

- Answers exactly one bounded question: "which task action next?"
  (observe / pick / place / verify / wait / abort + target).
- Implemented policies: FSMPolicy, JevPolicy with pluggable backends including
  ClefBackend, LLMPolicy, and HybridRouter (fast → slow → explicit FSM fallback).
- Clef confidence is routed through an FSM-action-agreement calibration, not a
  physical success or safety probability. See [MODEL_IDENTITY.md](MODEL_IDENTITY.md).
- Contract: pure `decide()` over canonical WorldState bytes + TaskGoal + Constraints +
  TaskHistory → `Decision(action, target, confidence, reason_code, evidence_ref)`.
- Byte-identical input for every policy; `notes[]` and free text excluded (#16).
- No safety authority, ever: no joint values, no motion scaling, no tolerance or budget
  control.

### Execution layer — HOW it is done (deterministic, no model)

- `task_fsm_server` today: admission/mutex, skill dispatch plumbing, cancellation
  semantics, evidence chain (run_id → step evidence_id), task-state topic,
  recovery-budget accounting (budget=1).
- Implemented deterministic safety gate (#6) validates every decision before
  dispatch (allowed-action menu, target existence, world freshness, revision gates,
  no policy free text in any goal field); invalid decisions are rejected typed and
  counted, never executed.
- World-revision gates on Pick/Place/MoveToPose goals already protect against stale
  decisions.

### Verification layer — WHETHER it worked (measured, not inherited)

- `verify_server`: independent gz ground-truth sampling vs expected; MISMATCH is an
  honest result, not a server failure.
- Pick physical check (box must follow the lift ≥ 0.03 m) · place drop check (0.06 m) ·
  reset canonical re-verification (±0.005 m) · strict lifecycle health gate
  (mainline readiness records 19 checks; historical delivery used 17).
- Executor-side `skill_contract.py` checks declared successes, while independent
  Verify/referee logic samples the simulation. Both still use simulation truth;
  no independent real-world sensor or physical safety certification is claimed.

## Canonical state & topics (v2 IMPLEMENTED, issue #3; policy input = versioned envelope)

| Topic                   | Producer                         | Content                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| ----------------------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/flexcell/world_state` | observe_server (single producer) | WorldState v2: revision counter, `source=SIMULATION_GROUND_TRUTH`, `schema_version="2.0"`, robot (+gripper aperture)/objects (+klass, pose_age_s)/carry/zones (+occupied_by); `TaskContext task` field is executor-owned at decide() time (default-empty from observe). Policy-facing bytes = `flexcell_skills.canonical_state` envelope, `WorldStateSchemaVersion=2`, `notes[]` stripped, deterministic (sort_keys + 9-decimal rounding); unit-tested 13/13 (`test/test_canonical_state.py`) |
| `/flexcell/carry_state` | carry_server (latched)           | backend **belief** — never physical evidence                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| `/flexcell/task_state`  | task_fsm_server (latched)        | IDLE / BUSY                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `/flexcell/inject`      | admin/benchmark                  | failure injection (`scenario:once\|always`) — seeded benchmark input                                                                                                                                                                                                                                                                                                                                                                                                                          |

Runtime component map (client/admin → run_demo & run_pick_place → task_fsm_server → six
skill servers → MoveIt / ros2_control / Gazebo; per-request JSONL evidence in
`~/.ros/flexcell/`): see WEEK2_PREPARATION §1.1 for the annotated diagram.

## Simulation manipulation backend

The default `teleport` backend pins objects to the measured end-effector offset
with a pose servo. The implemented `velocity_servo` alternative uses a leased
native pose/velocity constraint, engage receipt and release acknowledgment;
its evidence is separate from the Q8 teleport pilots. Both are magnetic simulation,
not contact grasping. This deliberate compromise is formalized in
[ADR/ADR-001-simulation-manipulation-backend.md](ADR/ADR-001-simulation-manipulation-backend.md):
the backend is replaceable; skill contracts must not depend on simulation shortcuts; a
future real-gripper backend replaces the implementation only.

## Pending integration and qualification

- [PR #28](https://github.com/Yenefa/flexcell/pull/28): reject hybrid evidence with
  no real fast calls/tokens; [PR #29](https://github.com/Yenefa/flexcell/pull/29):
  trustworthy grasp-probe terminal handling. Neither is part of this main snapshot.
- [TransferBench at 01fd76f](https://github.com/Yenefa/flexcell/tree/01fd76f):
  typed composite tasks, shared admission and confirmed-boundary pause/resume.
  Outer stage plans are caller-provided; this is not autonomous composition.
- Cross-arm grasp failures, complete model replay, portable E-021 Episodes and
  full M3 remain open. n≥50 and AC@90 remain frozen.
- [IYAIC preparation](../competition/iyaic-2026/README.md) reuses the runtime and
  evidence; it does not introduce another decision/control layer.
