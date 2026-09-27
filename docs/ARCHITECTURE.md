# ARCHITECTURE — FlexCell system

> Current state (Week-1.5 baseline, verified at delivery `7956d63`) and the ratified
> Week-2 target. The detailed design with `file:line` citations lives in
> [WEEK2_PREPARATION.md](WEEK2_PREPARATION.md); decisions live in [ADR/](ADR/); the
> decision-layer RFC is #14.

## Layered view

    Runtime Decision Layer        ← Week-2 target (does not exist yet; RFC #14)
            |  Decision objects only
    Task Executor                 ← today: task_fsm_server.py (frozen behavior)
            |  typed skill actions
    Skill Server                  ← observe / pick / place / verify / carry / move_to_pose
            |  ROS 2 topics & actions
    ROS 2 Jazzy / MoveIt 2        ← planning, execution, ros2_control
            |
    Robot Backend                 ← today: Gazebo Harmonic 8.15 sim (ADR-001); real arm later

Models may only decide **task-level actions**; they never control joints, trajectories,
parameters, or safety. That separation is enforced by the deterministic gate (#6), not by
policy goodwill.

## Pipeline: current vs future (M2.1 boundary freeze, ADR-002)

    CURRENT (Week-1.5, frozen):

        w1_client / admin
              │  /run_demo · /run_pick_place
              ▼
        task_fsm_server  (hard-coded FSM + bounded recovery)
              │  /observe · /pick_object · /place_object · /verify_object
              ▼
        Skills (observe · pick · place · verify · carry · move_to_pose)
              │
              ▼
        MoveIt 2 → ros2_control → Gazebo Harmonic (ADR-001 backend)

    FUTURE (M2+; default decision_policy=fsm is trace-identical to CURRENT):

        Policy (FSM │ Jev │ LLM │ Hybrid)
              │  Decision objects — the only channel down
              ▼
        Executor  (safety gate · dispatch · budget accounting · evidence)
              │  typed skill actions
              ▼
        Skills → ROS  (verification stays policy-blind, skill-side)

Boundary rules B1-B6 (typed channels, budget ceiling, gate-before-dispatch,
policy-blind verification, parity bar, replaceable parts) are frozen in
[ADR/ADR-002-runtime-decision-layer-boundary.md](ADR/ADR-002-runtime-decision-layer-boundary.md);
the line-anchored extraction map for `task_fsm_server.py` is its Appendix A.

## The three separated concerns

### Decision layer — WHAT to do next (models allowed here)

- Answers exactly one bounded question: "which task action next?"
  (observe / pick / place / verify / wait / abort + target).
- Fast policies: FSMPolicy / JevPolicy / HybridRouter; slow reasoner: LLMPolicy
  (deferred, ③).
- Contract: pure `decide()` over canonical WorldState bytes + TaskGoal + Constraints +
  TaskHistory → `Decision(action, target, confidence, reason_code, evidence_ref)`.
- Byte-identical input for every policy; `notes[]` and free text excluded (#16).
- No safety authority, ever: no joint values, no motion scaling, no tolerance or budget
  control.

### Execution layer — HOW it is done (deterministic, no model)

- `task_fsm_server` today: admission/mutex, skill dispatch plumbing, cancellation
  semantics, evidence chain (run_id → step evidence_id), task-state topic,
  recovery-budget accounting (budget=1).
- Week-2 additions: deterministic safety gate (#6) validating every decision before
  dispatch (allowed-action menu, target existence, world freshness, revision gates,
  no policy free text in any goal field); invalid decisions are rejected typed and
  counted, never executed.
- World-revision gates on Pick/Place/MoveToPose goals already protect against stale
  decisions.

### Verification layer — WHETHER it worked (measured, not inherited)

- `verify_server`: independent gz ground-truth sampling vs expected; MISMATCH is an
  honest result, not a server failure.
- Pick physical check (box must follow the lift ≥ 0.03 m) · place drop check (0.06 m) ·
  reset canonical re-verification (±0.005 m) · strict lifecycle health gate (17 checks).
- A decision policy can never inherit a success — the property that makes policy
  benchmarking trustworthy.

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

The carry skill pins objects to the measured end-effector offset via a 10 Hz `set_pose`
servo ("magnetic carry"). This is a deliberate compromise, formalized in
[ADR/ADR-001-simulation-manipulation-backend.md](ADR/ADR-001-simulation-manipulation-backend.md):
the backend is replaceable; skill contracts must not depend on simulation shortcuts; a
future real-gripper backend replaces the implementation only.
