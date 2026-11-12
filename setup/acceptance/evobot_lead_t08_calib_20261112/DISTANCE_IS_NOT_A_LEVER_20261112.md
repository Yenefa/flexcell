# `distance_m` is not a lever against the drag-back: the retreat takes more than the push gives

Round 64 established that seed 3002's push succeeds and the retreat drags the box back. The
obvious next question: if the retreat gives back a roughly fixed amount, pushing further should
net a gain. **It does not.**

## Test

`T08-push-seed3002`, biased staging (y = box_y + 0.07), two distances, one run each.

| `distance_m` | box start | furthest -x | box end | push | drag-back | net | zone distance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.090 | 0.1900 | 0.1900 | 0.1900 | **+0.0000** | +0.0000 | **+0.0000** | 0.1000 OUT |
| 0.130 | 0.1900 | 0.1730 | 0.1978 | **-0.0170** | **+0.0248** | **+0.0078** | 0.1078 OUT |

## What this rules out

**The drag-back scales with the push rather than being fixed.** At `distance 0.130` the box
advanced 0.0170 and was carried back 0.0248 - **the return exceeded the advance**, leaving the
box 0.0078 further from the zone than it started.

So increasing the commanded distance cannot win the race: the arm travels further, ends up
further past the box, and drags it further on the way out.

## What it also shows

At `distance 0.090` the box never moved at all. That is the same failure mode seed 3002 showed
in earlier rounds - `ee` motion with no contact - which means **this seed's outcome is not a
monotonic function of the push distance either.** 0.040 gave a net +0.033; 0.090 gave 0.000;
0.130 gave +0.0078. Three distances, three different behaviours, none of them a success.

## The conclusion this forces

A fix has to change **the retreat path**, not the push. The arm must withdraw vertically (or
otherwise clear the box) before moving in x. That is a change to how the push sequence ends,
which lives inside the push/recovery path - `contracts/push.py` is frozen, so the legitimate
route is `contracts/push_recover.py` or an interface that repositions after the push, both
inside `AUTHORITY_SCOPE.md` section 1.

**That has not been attempted.** This round only establishes that the cheaper options - offset
the approach, push harder - are exhausted.

## Not claimed

- Two runs. Not a rate.
- The 'retreat must clear the box' proposal is untested.
- T08 remains `CALIBRATION_UNSUPPORTED`; no capability claimed.