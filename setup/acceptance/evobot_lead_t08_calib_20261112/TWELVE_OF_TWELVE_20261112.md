# 12 of 12: with the staging move actually arriving, T08 push succeeds every time

Same 12-run design as round 70 - seeds 2000 and 3001, baseline vs retreat lift, three repeats
per cell - with one change: the harness now waits for `/arm_controller/follow_joint_trajectory`
before issuing the staging move.

## Results

| cell | stage | runs | zone distance | in zone |
| --- | --- | --- | --- | --- |
| 2000 / lift 0.0 | SUCCEEDED | OK, OK, OK* | 0.0228, 0.0442, 0.0129 | **3/3** |
| 2000 / lift 0.08 | SUCCEEDED | OK, OK, OK | 0.0309, 0.0229, 0.0299 | **3/3** |
| 3001 / lift 0.0 | SUCCEEDED | OK, OK*, OK | 0.0199, 0.0310, 0.0285 | **3/3** |
| 3001 / lift 0.08 | SUCCEEDED | OK, OK, OK | 0.0203, 0.0340, 0.0191 | **3/3** |

**12 of 12.** Every zone distance is between 0.0191 and 0.0442 against a 0.06 radius. **Every
staging move reported SUCCEEDED** - previously none ever did.

Against round 70's 8 of 12 with the same design and the same code, differing only in whether the
staging move reaches its target.

## My classification was wrong on the runs marked \*

The two cells marked `OK*` were labelled `NOOP` by the round-73 guard and are **not** no-ops:

```
2000/lift0.0 r3   push -0.1211   zone 0.0129
3001/lift0.0 r2   push -0.1324   zone 0.0310
```

Both pushed the box further than any other run in their cell and landed it inside the zone. The
guard flagged them because `ee_descent` fell below 10 mm - **and it fell because the staging move
succeeded.** The arm now starts at z 0.03 instead of 0.187, so there is almost nothing left to
descend.

**The `ee_descent` threshold is invalidated by this fix.** It measured "did the arm come down from
the neutral pose", which was a good proxy for "did it try" only while staging always failed. The
push magnitude and the direction cosine are the right signals now.

## What this changes, and the caution it needs

**The failure structure measured in rounds 70-74 was an artefact of a broken staging move.** That
work correctly characterised three failure modes, and all three were downstream of an arm that
started from the wrong place.

**But 12 of 12 is one batch.** Round 71's own lesson applies with full force: a change that looks
right in three runs has already failed to replicate once in this session, and 12 runs on 2 seeds
is still 2 seeds.

- Not scored by the frozen evaluator.
- No held-out seed tested.
- Mode C has not been seen since the fix, but it was 1 in 12 before and 0 in 12 now proves
  nothing about its rate.
- The retreat lift made no difference in this batch - both configurations went 6/6 - so its
  earlier "fixes one mode" reading may also have been a consequence of the broken staging.

## The next test

Held-out seeds with the fix in place, then the frozen evaluator on the satisfied runs. The
staging fix is a **harness** change (t08_timeline.py) and does not alter the robot's controller or
the task, so it does not by itself constitute a capability change - it removes a measurement
error that was masking what the robot can do.