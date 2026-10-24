# ARCHITECTURE — FlexCell system

> Current source: merged PR [#27](https://github.com/Yenefa/flexcell/pull/27),
> base `a9b6a62`, 2026-10-07. Runtime evidence is the archived E-020/E-021
> record; this document does not claim a live check of either robot host.
> The Week-1.5 behavior reference `7956d63` remains frozen.

## Current runtime

![Current runtime components](diagrams/current-architecture.svg)

[Editable Mermaid](diagrams/current-architecture.mmd) ·
[PNG preview](diagrams/current-architecture.png) ·
[Chinese diagram guide and development plan](ARCHITECTURE_AND_PLAN_20261007.md)

The diagram shows deployable runtime components. CLI clients and
`setup/94_scenario_runner.py` submit goals through `/run_demo` and
`/run_pick_place` to TaskFsmServer; lifecycle/admin reset and health operations
are a separate control path. Policies, the deterministic gate, recovery
accounting and episode recording are modules inside the task executor, rather
than additional services.

The decision layer, safety gate and episode seam **are implemented**. The
previous Week-1.5/current versus Week-2/future sketch described an earlier
source state. The ratified boundary remains
[ADR-002](ADR/ADR-002-runtime-decision-layer-boundary.md).

## Three responsibilities

**Decision — what happens next.** FSMPolicy, JevPolicy, LLMPolicy or
HybridRouter receives the versioned canonical WorldState plus TaskGoal,
Constraints and TaskHistory, and returns a typed Decision. Hybrid proposes
through the fast model, escalates below a supported confidence threshold, and
retains FSM fallback. Bootstrap before the first world observation uses FSM.
Policies cannot dispatch motion or change executor-owned safety parameters.

The current measured fast route uses Clef-Flash Q8 behind the typed
`/v1/systemone` interface; the slow route uses the official DeepSeek API.
The adapters remain replaceable. Local reproduction and TypeSafe adapters
exist in source; that does not establish qualification for those backends.
Model weights, loaded calibration, thresholds and runtime fingerprints are
recorded. Confidence and real token counts are telemetry, not physical success.

**Execution — how it happens.** TaskFsmServer owns admission/mutex, cancellation,
the action menu, dispatch, recovery budget, result interpretation and evidence.
Both RunDemo and RunPickPlace use the policy/skill seam. Every proposal passes
the deterministic gate before dispatch; only sanitized action/target fields
reach skills. Free-text explanations are evidence, not commands. Canonical state
comes from Observe; the executor adds the task portion.

**Verification — whether it worked.** SkillResult status and postconditions
prevent a default action result from masquerading as success. Pick checks that
the object follows the lift; Place confirms release and checks the drop;
Verify independently samples Gazebo ground truth against the target zone.
A backend's carry belief is not a measurement of a successful physical grasp.

## State, motion and persistence

| Interface               | Producer / owner           | Role                                                                                                                                                                      |
| ----------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/flexcell/world_state` | ObserveServer              | WorldState v2: robot, objects, carry and zones; revision and freshness. Policy bytes use `WorldStateSchemaVersion=2`, deterministic serialization and no notes/free text. |
| `/flexcell/carry_state` | CarryServer                | Latched carry belief. Observe obtains confirmed carry authority through `/flexcell/carry_snapshot` instead of trusting a stale cached topic.                              |
| `/flexcell/task_state`  | TaskFsmServer              | IDLE/BUSY lifecycle state.                                                                                                                                                |
| `/flexcell/inject`      | Benchmark/admin            | Sealed failure-injection input; arm/clear acknowledgments are checked.                                                                                                    |
| Episode JSON / JSONL    | Executor and skill servers | Exact policy inputs, proposals, selected actions, skill results, verifier results, timing and fingerprints.                                                               |
| Budget ledger           | LLM backend                | Persistent reservations and settlement against the operator's authorized spend.                                                                                           |

Pick and Place call MoveToPose, which drives MoveIt planning/execution;
ros2_control executes trajectories in Gazebo Harmonic. Carry uses the
deployment-selected magnetic backend: the original pose servo or
`velocity_servo_v1` with bounded pose/velocity control, leases and confirmation.
The Q8 E-020/E-021 evidence used teleport carry; the velocity implementation
has a separate E-015 evidence chain. They are not pooled.

Raw pose subscription and bounded pose RPC workers isolate native transport
from the ROS/admin parent. Health uses typed controller readiness and the
current 19-check strict gate. Reset must exit cleanly and restore the canonical
world; a success-looking JSON payload does not override a signal/crash.

## Evaluation seam and remaining work

The scenario runner resets the world, seals injection, dispatches a task,
matches the episode by evidence ID, checks the scenario and records its row.
FSM policy-input replay is distinct from model replay and Gazebo physics replay.
The metrics report recomputes results from recorded episodes.

The next PR adds hybrid batch qualification: fast-model presence and measured
tokens, calibration/fingerprint consistency, a separate batch audit, and
pre-dispatch smoke validation. An online run under the changed source requires
a new fingerprint and qualification. Runtime fallback behavior is unchanged.

E-021's n=20 control/low/high-threshold pilots have overlapping success-rate
intervals. Grasp failures remain an unresolved shared confounder; model replay
qualification and full M3 acceptance remain incomplete. n≥50 stays frozen.

[ADR-003](ADR/ADR-003-orchestration-substrate.md) places future MTC below the
executor at the skill seam. It is not another decision layer and is not
implemented. Contact grasping, camera observation and a real-arm backend remain
future work, triggered by measured needs and the relevant route decisions.
See [the planning diagram](diagrams/development-roadmap.svg) and
[ROADMAP](ROADMAP.md).
