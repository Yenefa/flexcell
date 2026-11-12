# The arithmetic, checked to three decimals

```
cube side                    0.035000
centre height upright        0.017500
centre height at 45 deg      0.024749      <- s * sqrt(2) / 2
predicted max rise           0.007249      <- (sqrt(2) - 1) / 2 * s
measured max z (seed 3001)   0.024690
measured rise vs 0.0175      0.007190      = 99.19% of the theoretical peak
bound max_lift_during_m      0.005000
bound / predicted rise       0.6898
```

## What the three numbers mean together

1. **The captured peak is 99.19% of the theoretical maximum.** The measurement is not missing the
   true high point - if anything the real peak is marginally higher than what was recorded, which
   only strengthens the conclusion.
2. **The bound is 69% of the rise that tipping this object necessarily produces.** Not "close to"
   or "sometimes exceeded" - structurally below it.
3. **The rise is a function of one number**, `(sqrt(2)-1)/2 * 0.035`, and no control parameter
   appears in it.

## Why this is the end of this line of inquiry

Every earlier blockage in this session was empirical: a parameter that might work, a mechanism
that might be avoidable. **This one is closed form.** A 35 mm cube that tips rises 7.249 mm.
The clause permits 5 mm. No pilot can thread that, and no amount of tuning changes the side of the
box.

## The three honest statements

- **The robot can do the task.** On the configurations that push, the box lands in the zone on
  four seeds, and `terminal_passed` was True on 7 of 18 runs with the other 11 failing on the tip
  rather than the placement.
- **The task as specified cannot be passed by this object.** Push it and it tips 7.25 mm against a
  5 mm bound; push low enough not to tip and it does not move at all - both ends measured.
- **The fix is not mine.** Raising `max_lift_during_m` above 7.25 mm, or widening the box base,
  are frozen-file changes requiring human approval. I have made neither.

## What must not be cited from this line

- **18/18** - withdrawn in round 84.
- **0/18 as evidence the robot cannot push.** It is evidence the clause rejects tipping, and the
  robot tips the box because that is what pushing a 35 mm cube does.
- **`CALIBRATION_UNSUPPORTED` as unresolved.** It is now resolved: the calibration is unsupported
  because the bound and the object are mismatched, and here is the arithmetic.