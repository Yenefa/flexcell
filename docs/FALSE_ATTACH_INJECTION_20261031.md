# A declared false attachment must stop the carry

Status: implemented, unit-tested, and declared as its own CI window. This is the
item that `DETACHABLE_ADMISSION_20261027.md` records as
"the false-attached rejection was tested through synthetic ROS/DDS telemetry, not
a live full-stack injection". It does **not** change D3: default admission stays
**NO_GO**.

## What a false attachment can and cannot be here

The joint backend is a Gazebo `DetachableJoint`: a rigid fixed constraint. A rigid
joint either holds or disappears — it cannot slip. So a genuine false attachment
(the gripper believes it holds a body that is actually separating) **cannot be
produced by this physics oracle**, and any claim to have produced one would be
false.

What can be produced is a lie at the point where the guard's contract begins: the
body still reports `joint_component: true` while its reported pose stops following
its parent. That is exactly the input the guard exists to police, so the injection
is applied there, and only there.

## The fixture

`FLEXCELL_FALSE_ATTACH=<box>:<offset_m>[:<hold_s>]`, parsed by
`contracts/injection.parse_false_attach` and refused at startup unless it is
exactly right (unknown box, other backend, offset outside (0, 0.1] m, hold outside
(0, 1] s, fewer than two 50 Hz frames).

Frozen values (`infra/joint-false-attach-window.json`, `scripts/false_attach_gate.py`):

| quantity | value |
| --- | --- |
| object | `target_box_a` |
| offset | 0.03 m, world +x |
| injection length | 0.2 s = 10 consecutive 50 Hz frames |
| first injected frame | ≥ 90 following samples (1.8 s) after attachment |
| boundary | `guard_input_pose` (the pose the guard is told, not the physics engine) |

`carry_server` displaces the reported pose of the target for exactly those frames,
then stops. The raw 2 ms step log is untouched: the altered frames are named in
`carry.jsonl` (`false_attach_injected`, with `first_sim_ns`/`last_sim_ns`), so the
audit trail keeps the injected frames separate from the physics record.

## What the window must prove

`false_attach_gate.verify_run` refuses the window unless all of this holds:

- the injection happened **exactly once**, on the declared object and session, with
  the declared offset/frames/axis/boundary, and not before the session had been
  following for 0.6 s;
- the guard latched the mismatch: `fault` non-empty, containing the *measured
  relative pose* reason, monitor no longer active;
- the displacement actually reached the sampled drift (≥ 20 mm), otherwise the
  guard was never lied to and the window proves nothing;
- the fault was not raised before the declared injection point (> 1.8 s of
  following), so the window cannot pass by failing early for another reason;
- the PICK failed **typed** (`error_code == 2`), its detail names the follow fault
  and a **confirmed** motion terminal, and never says `MotionTerminalUnknown`;
- no PLACE was dispatched after the refusal, and no success was claimed.

The evidence record states `boundary: guard_input_pose` next to
`interpretation: ... the fixed-joint oracle cannot slip physically, so this
qualifies the response chain only`.

## First window (local WSL, not CI)

`setup/acceptance/false_attach_20261031/` holds the receipt of one declared run
taken on the local WSL stack while GitHub Actions was refusing to start jobs:
window `FUNCTIONAL_WINDOW_PASS`, task `ERR_SKILL_FAILED` with
`PICK_A(attempt=1):FAIL:ERR_INTERNAL`, injection 10 frames at 32.882–33.062 s sim,
peak sampled drift 30.05 mm, `motion_error_code 32` with a confirmed terminal, no
PLACE dispatched, carry held for reconciliation. The same window and gate run in
CI (`false-attach-smoke`) once runners are available again.

## Boundaries

- This qualifies the **response chain** (guard → watch → cancel → confirmed stop →
  typed failure → carry held), not the physics of a slipping grasp. Contact grasp
  remains unmodelled.
- One task, one injection. No success rate, no MTBF, no D3 change.
- The injected frames are inside the sampled stream, so a reviewer can see both the
  injected values and the honest per-step log beside them. If they disagree, the
  window is refused.
