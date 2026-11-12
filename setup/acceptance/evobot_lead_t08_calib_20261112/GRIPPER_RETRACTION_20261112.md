# RETRACTION: the gripper aperture change is NOT a boundary artefact

Supersedes `GRIPPER_BOUNDARY_ARTEFACT_20261112.md`, which was wrong. That file is left in place
rather than deleted, because a retracted claim that disappears cannot be audited.

## What I claimed, and why it was wrong

I claimed the whole 0.0245 rad span came from a single final sample after the box had
stopped, and blamed `WorldState` reporting a default gripper position at goal completion.

**That was a sampling artefact of my own analysis.** I printed every 32nd sample of a
327-sample phase and drew a conclusion from 11 points. The values between them were never
looked at.

## What the full series shows

| phase | n | min | max | span | samples with abs(grip) > 0.006 |
| --- | --- | --- | --- | --- | --- |
| `push_1` | 275 | -0.000000 | 0.002910 | 0.002910 | **0** |
| `push_2` | 327 | -0.011150 | 0.013330 | 0.024480 | **50** |

Inside `push_2` the aperture **ramps continuously**:

```
t=15.41  grip=+0.007050
t=15.45  grip=+0.008140
t=15.48  grip=+0.009610
t=15.52  grip=+0.010700
t=15.55  grip=+0.011740
t=15.58  grip=+0.013030
t=15.62  grip=+0.013100
t=15.65  grip=+0.013330
```

That is a trajectory, not an outlier. Excluding each phase's final sample - the correction
I applied - changed the span **not at all**: 600 samples still span 0.024480.

## What this means

The fingers really do move during `push_2`, by 24.5 mrad, while the box is being moved.
`push_1` shows 2.9 mrad, which is inside the 0.0020 limit; `push_2` is 12x over it.

The most likely physical reading is that the fingers are **passive** and get squeezed open
or closed as the box is pressed against them - the gate's model of a deliberate grasp does
not fit a passive finger being deflected. `push_server.py:20-26` establishes that the
gripper is never commanded, so a change here can only come from contact, not from a command.

**This is not proven either.** Distinguishing passive deflection from a commanded closure
needs the gripper joint state read directly from `/joint_states` at the same instants, which
this run did not record.

## Why it still matters

The objective records the gripper gate as known to false-reject correct pushes. A passive
finger deflected by contact, measured against a 0.0020 rad threshold meant for commanded
closure, is a plausible mechanism for exactly that - and unlike my retracted version, it is
visible in 50 samples rather than one.

## What I did not do

- Did not relax the 0.0020 rad limit.
- Did not delete the wrong analysis.
- Did not claim the mechanism is established.