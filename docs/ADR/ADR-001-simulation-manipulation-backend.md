# ADR-001: Simulation Manipulation Backend Strategy

- **Status**: Accepted (2026-09-26; formalizes the Week-1 design decision, re-affirmed at
  Week-1.5 acceptance)
- **Context**: Week-1 implementation of pick/place over the simulation stack
- **Deciders**: chief review; recorded through the project maintenance process

## Context

FlexCell's research focus is **agentic workcell orchestration** — the decision layer,
policy benchmarking, and the evidence chain — not grasp physics. The runtime still needs
an object manipulation mechanism for pick/place.

The conventional route (contact/physics grasping via `DetachableJoint`) was tried first
and failed three independent ways: the robot-model-level subscriber disappears after the
first detach; world-level joint creation silently fails; a one-shot publish has a
discovery race that loses the message. The winning mechanism is a **transport-servo
magnetic carry**: `carry_server` pins the object to the measured end-effector offset at
10 Hz via `/world/.../set_pose` (pick freezes the offset, place releases it), with
success measured by independent truth (box-follow ≥ 0.03 m), never assumed.

## Decision

Keep the current carry backend (transport-servo magnetic carry) as the **simulation
manipulation backend**.

## Requirements going forward

1. The backend must remain **replaceable**. `CarryState` stays "backend belief, never
   physical evidence", and dispatch must never trust it without independent physical
   verification.
2. **Skill contracts cannot depend on simulation shortcuts.** The
   Observe/Pick/Place/Verify contracts and the measured-not-inherited doctrine are
   backend-independent.
3. A future real-gripper backend **replaces the implementation only** — no changes to
   skill action definitions, WorldState schema semantics, or the
   decision/execution/verification split.

## Consequences

- **Positive**: research velocity (no grasp-physics tuning); deterministic, repeatable
  demos; the decision layer and benchmarks are unaffected by a backend swap.
- **Negative / accepted risks**: magnetic ≠ contact grasping — no grasp-force realism
  and none of the failure modes of a real gripper; contact grasping remains a hardening
  candidate (together with carry chain-break detection).
- The swap is expected to be exercised by the **Real Robot Backend** phase
  ([ROADMAP.md](../ROADMAP.md)); the same replaceability rule then applies to the whole
  Robot Backend layer.

## 2026-10-01 implementation extension: leased velocity carry

The active mainline now selects `velocity_servo_v1`, retaining magnetic carry.
A world plugin constrains pose and velocity each physics step under a 500 ms
heartbeat lease, with session ownership and confirmed removal on release.
PICK waits for typed engage acknowledgement before lifting. The original
pose-only teleport backend remains available for archived conditions.

The skill action contracts and measured-rise / independent-verification rules
are retained. Statistical results are sensitive to the physics implementation:
old teleport and new velocity cohorts must use distinct deployment fingerprints
and must not be pooled. This extension does not introduce contact-grasp realism.
See [E-015 implementation and evidence](../CARRY_VELOCITY_20261001.md).
