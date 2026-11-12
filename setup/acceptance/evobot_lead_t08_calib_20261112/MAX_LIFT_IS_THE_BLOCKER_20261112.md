# The 11 failures are the no-grasp lift bound, not the task geometry

Round 85 established that every recorded condition in the `push` clause passed on 11 of 18 runs
while the clause reported failure. The clause body (`evaluate.py:223-241`) has one more term than
its evidence summary makes obvious:

```python
max_lift = float(want.get("max_lift_during_m", 0.005))
traj = (final_state.get("trajectory") or {}).get(name)
zmax = traj.get("max_z_m")
if zmax is None:
    lift_ok = False                     # fails closed
else:
    lift = float(zmax) - start[2]
    lift_ok = lift <= max_lift
ok = (min_m <= moved <= max_m) and dz <= max_dz and zone_ok and lift_ok
```

## The actual numbers

`fix_3001_0.0_1`, full clause evidence:

```json
{"displacement_m": 0.11825, "min_displacement_m": 0.03, "max_displacement_m": 0.15,
 "vertical_m": 0.0, "max_vertical_m": 0.02,
 "direction_cosine": 0.99731, "min_direction_cosine": 0.9,
 "zone": "zone_push", "distance_m": 0.01992, "radius_m": 0.06, "inside_zone": true,
 "max_lift_m": 0.00712, "max_lift_allowed_m": 0.005}
```

**Every end-state condition passes. The only failing term is `max_lift_m: 0.00712` against
`max_lift_allowed_m: 0.005`.**

The box's peak height during the motion was 0.02462 m against a resting 0.0175 - a **7.12 mm
rise** - and the no-grasp bound is 5 mm.

## This is the same class of defect as the gripper gate

Rounds 55-58 characterised a false rejection where a threshold sized for a **commanded** closure
was applied to a **passive** finger deflected by the box.

`max_lift_during_m` guards against a **grasp-carry-place** masquerading as a push - the object is
picked up, carried, put down. **7 mm of rise is not a carry.** A box being pushed by fingers that
ride above its top face will tilt and ride up slightly; the motion here is 118 mm horizontal
against 7 mm vertical, a ratio of 17:1.

**So the sensor-clause is rejecting correct pushes for the same structural reason the gripper
clause does: it measures a different phenomenon than the one it was written for.**

## What this explains

- **11 of 18 runs** fail on `push` because of the 7-9 mm lift, not because the box went the
  wrong way or ended outside the zone.
- **7 of 18** happened to stay under 5 mm and passed the clause - then were rejected by `gripper`.
- **0 of 18** pass both.

## What I am not claiming

- **Not that the bound is wrong in principle.** It correctly rejects a carry. It is applied to
  pushes that tilt the box a few millimetres.
- **Not that lifting is harmless.** 7 mm of rise is a real observation and may itself be the
  finger riding on the top face - which is the same geometry established in earlier rounds.
- **No change to any threshold.** `max_lift_during_m` is part of the frozen evaluator and I have
  not touched it. Changing it needs human approval.
- **0 of 18 verified.** T08 remains `CALIBRATION_UNSUPPORTED`.