# The lift bound cannot be satisfied by any contact height that also moves the box

Round 89 showed `max_lift` is the arc a 35 mm cube traces when it tips over: `(sqrt(2)-1)/2 * s`
= 0.00725 m. This round asks whether a lower contact point avoids the tip - it does, and then the
box does not move at all.

## The full sweep

| contact_height | lift | against 5 mm bound | displacement |
| --- | --- | --- | --- |
| 0.0200 | 0.00712 | **OVER** | **0.107** |
| 0.0150 | 0.00721 | **OVER** | moves |
| 0.0125 | 0.00708 | **OVER** | moves |
| 0.0080 | **0.00149** | **UNDER** | **0.0000** |
| 0.0050 | **0.00256** | **UNDER** | **0.0000** |

**There is no value in between that was tested and none is suggested by the two ends.** Above
about 0.0125 the box is pushed and tips; at 0.008 and below it does not tip because it is not
pushed.

## Why 0.005 is the floor

`push_server` logs `contact_floor=0.0050m` at start-up, so 0.005 is the lowest the interface
accepts. **The entire admissible range has now been sampled, and it is empty of a working point.**

## What this means

The task, as specified, has a physical contradiction for this object:

- **Push it** and a 35 mm cube tips, rising `(sqrt(2)-1)/2 * 0.035 = 7.25 mm`, against a 5 mm
  no-grasp bound.
- **Do not tip it** by pushing low, and the fingers pass under the box without moving it, so
  displacement is 0 against a 0.03 m floor.

**No contact height satisfies both.** The bound and the object are mismatched.

## What this does not excuse

- **The robot is not failing to do the task.** On five configurations that actually push, it lands
  the box in the zone; the clause fails on the tip, not the placement.
- **But nothing here licenses calling T08 solved either.** 0 of 18 verified, and the run that would
  verify it does not exist under the current bounds.

## The two changes that would be needed, neither of which I may make

1. **Raise `max_lift_during_m` above 7.25 mm** for this object - frozen evaluator, human approval.
2. **Or widen the box's base** so tipping raises less than 5 mm - a TaskSpec change, frozen.

Both are outside my authority. The correct engineering answer is that a no-grasp bound must be
calibrated against the object it is applied to, and `max_lift_during_m` states its value without
stating what it was calibrated on.

## Status

**T08 remains `CALIBRATION_UNSUPPORTED`.** 0 of 18 Independently Verified. No threshold, TaskSpec
or evaluator file was modified.