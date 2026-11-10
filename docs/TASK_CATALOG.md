# EvoBot Task Catalog

Status per template uses the evidence ladder from `docs/EVOBOT_VISION.md`.
**No template has been executed on the robot yet** — the generator and evaluator are
unit tested, the tasks themselves are not.

## Phase 1 — Composition of existing skills (T01-T06)

These need `pick`, `place`, `verify` and `move_to_pose`, all of which exist. The
difficulty is deciding what to do, not building a new primitive.

| ID | Template | Capability tested | Bottleneck | Status |
| --- | --- | --- | --- | --- |
| T01 | `T01_multi_object_sorting` | assign each object its own destination | multi-target planning | Implemented, Unit Tested |
| T02 | `T02_exclusion` | move everything except one | constraint comprehension; must prove non-action | Implemented, Unit Tested |
| T03 | `T03_ordered` | obey a stated order | sequence tracking across steps | Implemented, Unit Tested |
| T04 | `T04_duplicates` | distinguish two identical-looking objects | instance identity, not appearance | Implemented, Unit Tested |
| T05 | `T05_relay` | route via an intermediate bin | multi-stage, state carries between stages | Implemented, Unit Tested |
| T06 | `T06_revisit` | move an object twice, only final counts | memory across instructions | Implemented, Unit Tested |

### What each one actually costs the agent

- **T01** is the easiest: two independent pick-and-place. If the agent cannot do this,
  nothing above it is meaningful.
- **T02** is the first one where not acting is part of the answer. An agent that
  clears the whole table fails.
- **T03** separates doing the right thing from doing it in the right order — the
  evaluator checks order independently of the final positions.
- **T04** removes the colour shortcut. The two blocks look alike, so the agent must
  use measured geometry rather than appearance.
- **T05** forces a multi-stage plan with an intermediate checkpoint.
- **T06** requires holding instruction state: the first placement is wrong by the end
  of the instruction, and only the final position is graded.

## Phase 2 — New physical skills (T07-T10)

| ID | Template | Needs | Why it cannot be emitted yet |
| --- | --- | --- | --- |
| T07 | `T07_stacking` | place on top of another box | no primitive places at a stacked height; release clearance is set for table height |
| T08 | `T08_push` | push by end-effector contact, no grasp | nothing currently contacts a box side; all motion targets are grasp poses |
| T09 | `T09_clutter` | work among distractors | three objects exist but no collision-aware placement for extra obstacles |
| T10 | `T10_constrained_placement` | place under spatial constraint | needs a constrained scene variant, which is its own experiment |

These are registered so the gap is visible. `generate.py` raises
`NotImplementedError` for them rather than emitting a spec with invented
expectations — a task whose success condition is guessed is worse than no task.

## Phase 3 — Open-ended

Not registered. Directions only: tool use, assembly, insertion, multi-stage, dynamic
obstacles, unknown-object adaptation, long-horizon, novel composition. Each requires
kinematic and reachability validation before it can become a template.

## Feasibility notes for the current arm

| Constraint | Value | Consequence |
| --- | --- | --- |
| reach | ~380 mm | all bins and boxes are within 300 mm of the base |
| payload | 500 g | boxes are 50 g; not a limiting factor |
| gripper | 2-finger, opens to 20 mm | 35 mm boxes are gripped from outside; placement needs 10 mm clearance |
| joints | 4 + gripper | no wrist roll, so object yaw control is limited — tasks requiring precise re-orientation are out of scope |
