# Gripper aperture: the 0.0245 rad is a boundary artefact, not a grasp

Round 53 run (`/tmp/onesrc`), frozen evaluator `0.5.0`, task `T08-push-seed3001`.

## What the gate said

```
gripper :: gripper aperture changed by 0.0245 rad during the window (limit 0.0020);
           fingers closing on an object is a grasp, not a push
```

Read as physics, that says the fingers closed on the box and the run was a carry.

## What the series actually shows

| phase | samples | grip span (rad) | box travel (m) |
| --- | --- | --- | --- |
| `push_1` | 327 | 0.002910 | 0.1371 |
| `push_2` | 327 | 0.024480 | 0.0703 |

All of the 0.0245 is inside `push_2`. Inside `push_2`:

```
t= 8.76  box_x=0.0929  grip= 0.000000
t= 9.79  box_x=0.0929  grip= 0.000000
t=10.85  box_x=0.0474  grip= 0.000000
t=11.94  box_x=0.0457  grip=+0.000430
t=13.97  box_x=0.0457  grip=+0.002910
t=15.07  box_x=0.0454  grip=+0.000180
t=16.18  box_x=0.0417  grip=+0.000950
t=17.30  box_x=0.0381  grip= 0.000000
t=18.48  box_x=0.0264  grip= 0.000000
t=19.64  box_x=0.0199  grip= 0.000000
t=20.84  box_x=0.0226  grip=-0.011150   <- last sample, box already stopped
  done            grip=-0.011000
```

The fingers read 0.000 at every sampled instant while the box is being moved. The
outlier appears on the **final** sample, after motion has ended, and persists into the
`_done` marker. The verifier measures the span across that transition.

## Most likely mechanism

`WorldState` appears to report a default or unset gripper position once the goal has
completed, and the sampler keeps recording across that boundary. This is a sampling
artefact, not contact.

**Not proven.** An alternative is that the gripper joint is genuinely perturbed during the
retreat at the end of `push_2`. Distinguishing them needs the gripper joint state read
directly from `/joint_states` at the same instants, which this run did not record.

## Why this matters

The objective statement records the gripper gate as **known to false-reject correct
pushes**, and that is part of why T08 is `CALIBRATION_UNSUPPORTED`.

This is the first concrete mechanism this session has produced for such a false
rejection: a boundary sample entering the aperture span. It is **one demonstrated path**,
not proof that it is the whole known defect, and it is not claimed as such.

## The fix, and the fix that is not allowed

Allowed: stop the aperture series at the action boundary, or exclude the completed-goal
sample. That is a change to `t08_timeline.py` sampling.

Not allowed, and not done: relaxing the 0.0020 rad limit. A threshold that rejects a
carry must not be widened to admit one, and the gate exists precisely to keep a push
distinguishable from a grasp.