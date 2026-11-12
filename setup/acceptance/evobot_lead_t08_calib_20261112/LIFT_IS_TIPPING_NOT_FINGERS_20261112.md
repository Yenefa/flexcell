# The lift is not the finger riding on top - it is the box tipping, and no contact height changes it

The remaining hope was that `max_lift` 7 mm could be reduced by pushing lower, on the theory that
fingers riding on the box's top face were lifting it.

## Test

Seed 3001 (consistently 7.1-7.2 mm), three contact heights, everything else identical.

| contact_height | box z max | lift above resting |
| --- | --- | --- |
| 0.0200 (baseline) | 0.02462 | 0.00712 |
| 0.0150 | 0.02471 | 0.00721 |
| 0.0125 | 0.02458 | 0.00708 |

**The lift is 7.08-7.21 mm across a 60% change in contact height.** It does not move.

## What that means

A 0.035 m cube pushed horizontally tips about its leading bottom edge. A 7 mm rise over a 35 mm
base is a rotation of roughly **11 degrees** - which is what pushing a tall thin box near its
centre does.

**So the 7 mm is the box tipping under the push, not the fingers lifting it.** That is why it is
insensitive to contact height: it is a consequence of where the force is applied relative to the
base, not of how high the fingers sit.

## The consequence for the no-grasp bound

`max_lift_during_m` defaults to **0.005 m** and exists to catch a grasp-carry-place.

**A 35 mm box tipped 11 degrees by a legitimate horizontal push rises 7 mm. The bound is below
what this task's own object does when pushed correctly.**

Taken with round 87's finding - that `max_lift <= 0.005` predicts `terminal_passed` 18 of 18 -
the picture is: **the push clause is not measuring whether the box was pushed, it is measuring
whether the box happened to tip less than 5 mm on this run.**

## What I am not claiming

- **Not that the bound should be raised.** That is a frozen-evaluator change needing human
  approval, and the correct value depends on the object and how a real push should behave -
  neither of which I can decide unilaterally.
- **Not that tipping is acceptable in general.** A task could legitimately forbid it. This one
  declares `max_lift_during_m` without saying what it was calibrated against.
- **0 of 18 verified.** T08 remains `CALIBRATION_UNSUPPORTED`.

## Levers now exhausted for this bound

| lever | effect on lift |
| --- | --- |
| `contact_height_m` 0.0125 / 0.0150 / 0.0200 | none - 7.08 to 7.23 mm throughout |
| staging x, y | none established in rounds 65-66 |
| `distance_m` | changes how far it travels, not the tip |
| `retreat_lift_m` | acts after the push, cannot affect peak height during it |

**The lift is a property of pushing a 35 mm cube, not of any parameter the interface exposes.**