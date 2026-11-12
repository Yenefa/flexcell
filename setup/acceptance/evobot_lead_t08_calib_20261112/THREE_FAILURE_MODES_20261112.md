# Three seeds, three different failure modes - and one is a REVERSAL reported as cosine +0.992

Identical parameters, single staged push, `contact_height 0.020`, `distance 0.040`, direction -x.

## seed 3001 - succeeds

```
first t=0.36  ee=(0.2860, 0.0000, 0.1872)  box=(0.2300, -0.0700, 0.0175)
last  t=8.21  ee=(0.2745, -0.0735, 0.0194) box=(0.1188, -0.0628, 0.0175)
closest ee-box 0.0509 m
```

Box travels **-0.1112 m in x** - the commanded direction. `cos +0.9979`.

## seed 3002 - never executes

```
first t=3.47  ee=(0.2860, 0.0000, 0.1872)  box=(0.1900, 0.0200, 0.0175)
last  t=4.59  ee=(0.2860, 0.0000, 0.1872)  box=(0.1900, 0.0200, 0.0175)
```

**The end effector never moves. Not slightly - identically, to four decimals, from first
sample to last.** The push phase lasts 1.12 s where seed 3001's lasts 7.85 s. `contact=False`.

This is not a failed push; it is a push that did not run.

## seed 2000 - REVERSAL, reported as a correct direction

```
first t=0.37  ee=(0.2860, 0.0000, 0.1872)  box=(0.2200, 0.0000, 0.0175)
last  t=7.22  ee=(0.2640, 0.0025, 0.0200) box=(0.2462, 0.0023, 0.0169)
closest ee-box 0.0044 m at t=4.06
```

**The commanded direction is -x. The box moved +0.0262 in x - the opposite way.**

The end effector moved -0.0220 in x, so the arm went the right way and the box went the wrong
way. The closest approach was 4.4 mm, close enough that the gripper was in contact.

**And `direction_cos` reported +0.9920.**

## Why the cosine is worthless here

`displacement_along_direction_m` is what the skill reports, and `direction_cos` is derived from
it. For seed 2000 the box moved +0.0262 while the commanded direction was -1.0 in x, so the
true signed displacement along the commanded direction is **-0.0262** and the true cosine is
**-1.0**, not +0.9920.

**The reported value has the wrong sign.** This is the same class of discrepancy recorded
earlier in this session as `direction_cos +0.999` while the box went the other way, and it is
still present.

## This is the reversal, and it is reachable in a plain run

The objective records the recovery loop's backward-push mechanism as UNKNOWN, with the client
hypothesis rejected. **This is a reversal in a plain T08 push, with no recovery loop involved,**
where the arm moves in the commanded direction and the box goes the other way.

The likely mechanism is the finger geometry already established: fingers sit behind the
end-effector frame and above the box top at the approach pitch, so the gripping surface can
arrive on the far side of the box and drag it back rather than pressing its near face.
**Hypothesis, not established.**

## Not claimed

- One run of each mode. These are existence proofs, not rates.
- The cosine-sign defect is demonstrated on one run.
- No fix is proposed here.