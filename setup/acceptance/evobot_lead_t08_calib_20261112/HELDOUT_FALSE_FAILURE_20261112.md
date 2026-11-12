# A held-out run passes every task clause and is rejected on the gripper gate

`T08-push-seed3000`, round 82 batch, untouched by any tuning, run through the frozen evaluator
`0.5.0` with the full evidence chain.

## Verdict

```
terminal_passed             True
clause unmoved:target_box_b -> True
clause push:target_box_a    -> True
passed                      False
evidence_status             COMPLETE_EVIDENCE_CONTRADICTS_PUSH
false_success               False
false_failure               False
gates                      8 / 10
```

**The task succeeded by every clause the task defines, and the run was rejected.**

## The one failing gate

```
gripper :: gripper aperture changed by 0.0068 rad during the window (limit 0.0020);
           fingers closing on an object is a grasp, not a push
```

3.4x over the limit.

## Why this is the same false rejection already characterised

Rounds 55-58 established the mechanism by code path:

- `observe_server.py:214` reads `gripper_position` from `/joint_states` - **measured** joint
  position, not a command echo.
- `push_server.py:20-26` establishes the gripper is **never commanded** during a push, and must
  not be, so a push stays distinguishable from a carry.

**Both fingers appear in the contact trace for this run** (`gripper_left_link` and
`gripper_right_link`, 2 pusher links). Neither was commanded. The aperture moved because the box
pressed on the fingers while being pushed.

## What is different from round 58

Round 58 demonstrated this on a **tuning** seed, as a single instance. This is a **held-out**
seed, and it is the second independent instance.

**Two instances is not a rate, but it is no longer a one-off.**

## The consequence for T08's status

The objective records T08 push as `CALIBRATION_UNSUPPORTED` because the gripper gate is known to
false-reject correct pushes.

**This run is direct evidence for that recorded claim, produced independently of it:** the task
clauses pass, the evidence is complete, and the verdict is rejection on a gate whose threshold is
sized for a commanded grasp applied to a passively deflected finger.

## What I am NOT claiming

- **Not Independently Verified.** The frozen evaluator rejected this run. That is the whole point
  of the distinction.
- **The 18/18 from rounds 81-82 is not 18 verified successes.** Some of those would be rejected
  the same way; this is the first one measured.
- **The gate is not wrong for its own purpose.** 0.0020 rad is a reasonable bound on a commanded
  closure. The defect is that it is applied to a different phenomenon.
- Nothing here proposes a fix. Changing the gate is a frozen-file change requiring human approval
  and is outside my authority.