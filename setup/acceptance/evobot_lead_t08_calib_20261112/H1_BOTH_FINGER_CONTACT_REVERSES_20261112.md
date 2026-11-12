# H1 FOUND: fingers touch the box on BOTH sides only when the box is aligned with the gripper axis, and that run goes backwards

This is the separation of H1 (contact geometry not re-established) from H3 (controller not
executing the commanded trajectory) that the objective lists as the second critical-path item.

## The three runs, identical parameters

| seed | box y (from zone) | ee y at staging | lateral offset | right-finger contacts | left-finger contacts | result |
| --- | --- | --- | --- | --- | --- | --- |
| 3001 | **-0.07** | 0.00 | **0.07** | 665 | **0** | pushed -x, correct |
| 2000 | **0.00** | 0.00 | **0.00** | 451 | **383** | pushed **+x, reversed** |
| 3002 | +0.02 | 0.00 | 0.02 | 0 | 0 | never executed |

Box y is read from the task's `zone_push` pose, which sits directly under the target box:
seed 3001 zone (0.13, -0.07), seed 2000 zone (0.12, 0.0), seed 3002 zone (0.09, 0.02).

The staging point is `(0.35, 0.00, 0.03)` in every run, so the end effector's y stays at 0.00.

## The mechanism

**When the box is laterally offset from the gripper axis, only one finger can reach it.** The
gripper arrives beside the box and the near finger presses a side face - the box goes the
commanded way.

**When the box is aligned with the gripper axis, both fingers arrive on opposite sides of it.**
The box is then between the jaws, not in front of them, and the motion drags it backwards.

That is contact geometry, not control. The arm moves -x in both runs; seed 2000's end effector
travelled -0.0220 in x while the box went +0.0262. **H3 is excluded for this run: the
controller executed the commanded trajectory.**

## Why this matters

The objective records the backward-push mechanism as UNKNOWN with the client hypothesis
rejected. This gives it a concrete geometry: **both-finger contact produces the reversal**, and
both-finger contact happens exactly when the box is centred on the gripper.

It also explains why the round-49 measurement of 'only gripper_right_link touches' was true
for that run and false as a general statement: seed 2000 has 383 left-finger contacts.

## The testable consequence

If the mechanism is right, moving the staging point's **y** to match the box's y - so the
gripper arrives off-axis on every run, not only when the seed happens to place the box off
the centreline - should make the reversal disappear.

**That is a prediction, and it is falsifiable.** It has not been run.

## Scope note

Changing the staging point is inside the granted authority: `AUTHORITY_SCOPE.md` section 1
covers 'interfaces required for safe re-positioning - anything I must call to put the arm back
on a legal contact side'. `contracts/push.py` is untouched by this - the staging move is issued
before the push, through `move_to_pose`.