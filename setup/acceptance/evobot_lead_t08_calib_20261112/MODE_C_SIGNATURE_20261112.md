# Mode C identified: `error_code 30`, `increments_executed 0`, and the action returns in 0.3 s

The no-op run from round 70 (`seed 3001, lift 0.08, repeat 3`) returns:

```json
{"outcome": 1, "error_code": 30, "displacement_m": 0.0,
 "displacement_along_direction_m": 0.0, "direction_cos": 0.0,
 "contact_made": false, "ee_travel_m": 0.0,
 "reach_error_m": 0.0, "increments_executed": 0}
```

**`increments_executed: 0`.** The push is designed to execute in increments; this run executed
none of them. `ee_travel_m: 0.0`, so the arm never moved.

## The timing

```
initial      t=0.33  ee_z=0.18715
push_1       t=0.36  ee_z=0.18715   <- phase opens
push_1_done  t=0.66  ee_z=0.18722   <- phase closes, 0.30 s later
```

**Three tenths of a second.** A real push in the same batch runs 7-8 seconds. This is not a push
that failed partway - it returned almost immediately.

## What it is not

- **Not a refusal over `contact_height_m`.** The server logs
  `contact_height=UNSET (request must declare it)`, but the request DID declare it:
  `t08_timeline.py` passes `CONTACT_Z = 0.0200` and sets `g.contact_height_m = CONTACT_Z`. The log
  line is the server's start-up banner, not a per-request complaint.
- **Not a reach failure.** `reach_error_m: 0.0`.
- **Not a crash.** `outcome: 1`, so the action reported a normal result.

## The signature that can detect it automatically

`error_code == 30` **and** `increments_executed == 0` **and** `ee_travel_m == 0.0` together
identify mode C exactly, from the action result alone - no pose series needed.

That is a better detector than the `ee_descent_m` guard added in round 73, which infers the same
thing from the timeline. **Both should stay**: the action result is authoritative when present,
and the pose guard still works if the result is lost.

## Mode B, for contrast

The `2000 / lift 0.08 / r2` failure returned a real push that went badly: the arm descended
(ee z 0.0212), 946 gripper-box contacts were traced, and the box ended 1.9 mm from where it
started. **Different signature, different cause, and it is not a no-op.**

## What is still unknown

**Why `error_code 30` with zero increments.** The result tells us the push did not start; it
does not say what stopped it. Candidates are a pre-flight check inside the push path and a
controller state left over from the staging move. Not investigated.

## Not claimed

- One observed instance. `error_code 30` may cover more than one condition.
- The detector is described, not added to the analysis code.
- T08 remains `CALIBRATION_UNSUPPORTED`.