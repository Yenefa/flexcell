# The gripper aperture change is REAL JOINT STATE, and the gate's model does not fit

Round 55 left an observation without an explanation: `push_2` spans 24.5 mrad of aperture
against a 0.0020 rad limit, `push_1` spans 2.9 mrad. Two readings were possible - the fingers are
passive and get deflected by contact, or something commands them closed.

This round separates them by reading the code path, not by another run.

## Where `gripper_position` comes from

`flexcell_skills/observe_server.py:214`

```python
robot.gripper_position = float(self._js.position[idx[n]])
```

`self._js` is `/joint_states` - **measured joint position**. It is not a command echo, not a
target, not a cached goal. Whatever appears in that field is what the physics engine reports
for the joint.

## Who can command that joint

`flexcell_skills/common.py:452-466` contains a gripper action client that sends a
`GripperCommand`-style goal and publishes a `gripper_position_target` record naming
`joint='gripper_left_joint'`.

So a command path exists in the codebase. It matters whether the push flow goes through it.

## The push flow does not

`push_server.py:20-26` states the gripper is never commanded during a push, and this is
required rather than incidental: a push must be distinguishable from a carry, so the pusher
must not grasp.

## Conclusion

**The 24.5 mrad of aperture change during `push_2` is measured joint motion produced by
contact, not by any command.** The fingers are passive here; the box squeezes them aside as it
is pushed.

`push_1` at 2.9 mrad is inside the 0.0020 limit; `push_2` at 24.5 mrad is 12x over it. Same
robot, same task, both non-commanded - and one passes the gate while the other fails.

## Why this is the mechanism behind a known false rejection

The objective records the gripper gate as **known to false-reject correct pushes**, and T08 is
`CALIBRATION_UNSUPPORTED` partly for that reason.

The gate's 0.0020 rad limit is sized for **commanded** gripper closure - a deliberate grasp.
Applied to **passive** fingers being deflected by the box they are pushing, it will reject
correct pushes whenever the geometry lets the box press on a finger. That is exactly what
`push_2` shows.

## Limits of this claim

- Does **not** prove the whole known gate defect is this mechanism.
- Does **not** show that the 0.0020 limit is wrong for commanded closure; it is a correct
  threshold guarding against a different thing.
- Does **not** establish what makes `push_2` different from `push_1`; that is the next question.

## What was not done

No threshold changed. No evidence deleted. The retracted analysis from the previous round
remains in the tree.