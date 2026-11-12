# The push clause failed because the sampler runs TWO pushes, and the second one overshoots

`T08-push-seed3001`, round 53 capture (`/tmp/onesrc`), frozen evaluator `0.5.0`.

## The failure

```
clause push:target_box_a -> False
```

The obvious suspects were direction, displacement and the gripper, all of which were being
investigated. None of them is the cause.

## The arithmetic

Task `T08-push-seed3001`:

| limit | value |
| --- | --- |
| zone | `zone_push` at (0.13, -0.07), radius 0.06 |
| min displacement | 0.03 m |
| max displacement | 0.15 m |
| min direction cosine | 0.9 |

Box position at each phase boundary, from the timeline:

| phase | t | box (x, y) | distance to zone centre | inside zone |
| --- | --- | --- | --- | --- |
| `initial` | 0.53 | (0.2300, -0.0700) | — | — |
| `push_1_done` | 8.72 | (0.0929, -0.0720) | **0.0372** | **YES** |
| `push_2_done` | 21.11 | (0.0226, -0.0471) | **0.10981** | **NO** |

Total displacement from start to finish: **0.20865 m**, against a 0.15 m ceiling.

## What actually happened

**`push_1` succeeded.** After it, the box sits 0.0372 m from the zone centre - well inside the
0.06 radius - having moved 0.1371 m, which is inside the 0.03-0.15 window, at cosine 0.9999.

`push_2` then ran and pushed it a further 0.0746 m, out of the zone and past the maximum
displacement.

**The task failed because a second push undid a successful first one.**

## Why two pushes happened

`t08_timeline.py` was written to sample a push and it calls `push_once()` more than once to
get repeated measurements. That is fine for a diagnostic that wants two samples. It is not a
task execution: the graded run must stop when the task is satisfied.

`candidate_staged_push.py`, which is the actual candidate, does exactly one push. **The two-push
behaviour is in the sampler I wrote this round, not in the candidate.**

## Consequence for everything measured since round 53

Every bundle built from this capture inherits the second push: the final position is the
post-`push_2` position, so the push clause cannot pass, and the `gripper` aperture span covers
both pushes rather than one.

The 24.5 mrad finding stands - it is measured joint state during `push_2` - but it is the
aperture of a push that should not have been issued.

## The fix

One push per graded run. The sampler takes a repeat count and it must be 1 when the run is
being graded rather than probed. No threshold, no evaluator, no TaskSpec changes.