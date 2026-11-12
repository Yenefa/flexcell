# The box does not tilt 11 degrees - it tips over 92 degrees, and 7.25 mm is the geometry of that

The round-88 estimate of an 11 degree rotation was inferred from the height rise alone. The
contact trace records the box's quaternion, so it can be measured directly.

## The box's actual orientation through one push

| sim_ns | box z | rotation from upright |
| --- | --- | --- |
| 5 ms | 0.01750 | 0.00 deg |
| 3885 ms | 0.01750 | 0.00 deg |
| 4855 ms | 0.01750 | 0.00 deg |
| 5825 ms | 0.02000 | 12.06 deg |
| 6795 ms | 0.02245 | 21.38 deg |
| 7765 ms | **0.02469** | 50.38 deg |
| 8735 ms | 0.01726 | **92.13 deg** |
| 9705 ms | 0.01746 | 92.61 deg |

**The box tips over and lands on its side.** 92 degrees is a full quarter turn - it does not
tilt, it rolls.

## The arithmetic matches exactly

A cube of side `s` rotating about a bottom edge lifts its centre by:

```
max rise = (sqrt(2) - 1) / 2 * s
         = 0.2071 * 0.035
         = 0.00725 m
```

**Measured: 0.00708 to 0.00723 m across every contact height tried.** The prediction is 0.00725.

## What that settles

`max_lift_during_m` is **0.005 m**. The geometry of this task's own object, tipping over during a
correct push, produces **0.00725 m**. The bound sits **31% below** a value that is fixed by the
box's dimensions alone.

**No control parameter can reduce it, and rounds 65-66 and 88 confirmed that empirically for
distance, staging x and y, contact height, and the retreat lift.** A parameter change cannot alter
`(sqrt(2)-1)/2 * 0.035`.

## Why this closes the question rather than reopening it

Round 87 showed `max_lift <= 0.005` predicts `terminal_passed` 18 of 18. Round 88 showed contact
height does not move the value. This round shows why: **it is not a control outcome at all, it is
the arc a 35 mm cube traces when it goes over.**

## What I am still not claiming

- **Not that the bound is wrong for its purpose.** It catches a grasp-carry. It also rejects any
  push that tips the object, and this object tips.
- **Not that tipping is desirable.** A task could reasonably forbid it - but then the box needs a
  wider base or the push needs a lower contact point, and neither is a parameter I can set.
- **No threshold changed.** `max_lift_during_m` is inside the frozen evaluator.
- **0 of 18 verified.** T08 remains `CALIBRATION_UNSUPPORTED`, now for a reason that is arithmetic
  rather than empirical.