# Mode C traced to its cause: `move_to_pose` failed TWICE, and the push never had a chance

Round 75 identified mode C's signature - `error_code 30` (`ERR_MOTION_FAILED`),
`increments_executed 0`, a 0.3 s return. `contracts/push.py:417-422` shows what that means:

```python
ok, reach_err, detail = io.move_to(approach)
if not ok:
    return finish(OUTCOME_FAILED, ERR_MOTION_FAILED, 'approach failed: %s' % detail)
```

So mode C is an **approach** failure. The per-run `move_to_pose.jsonl` for the no-op shows what
the approach and the staging move before it actually did:

```
[0] request_id 'stage'         target [0.35,   0.00, 0.03]   outcome FAILED
[1] request_id 'target_box_a'  target [0.2675, -0.07, 0.02]   outcome FAILED
```

**Both moves failed.** The staging move failed, so the arm stayed at its neutral pose; the
approach then failed too, so `push.py` returned `ERR_MOTION_FAILED` in 0.3 s with zero
increments. The push was never the problem - it never received a moved arm.

## Why this matters more than the push-side story

Rounds 61-69 treated the failure as a push and retreat problem and got real answers (drag-back,
retreat clearance). **Mode C sits upstream of all of it.** If `move_to_pose` fails, nothing
downstream is meaningful, and no push-side parameter can help.

## The guard I added covers only part of this

`stage_ok` was added to `candidate_staged_push.py` in an earlier round and checks the pitch after
the staging move. **`t08_timeline.py`, the harness used for every measurement in rounds 60-74,
does not check it.** It ran the staging move and proceeded regardless of the outcome.

That is the same silent-failure pattern this session has now hit three times: round 53 (staging
move returning without effect), round 60 (seed 3002 zero run), round 70 (this one). Each time the
lesson was 'check the action result', and each time the check was added in one place and not
propagated.

## What is NOT explained

**Why `move_to_pose` failed.** The log records `outcome FAILED` with no reason field captured in
this build. Candidates: IK unreachable for the staging point, a controller state left over from a
previous run in the same process, or a timeout. **Not investigated** - the next run needs the
detail string, which `push.py` captures for the approach but `move_to_pose.jsonl` apparently does
not for the staging move.

## Consequence for the measurements

One of the twelve runs in the round-70 batch is mode C. **That run is not evidence about pushing**
and should be excluded from any capability rate, not counted as a failure. The 4/6 figures in
round 74 are unaffected numerically (that run was already a failure) but their interpretation is:
one of the four failures in each configuration is an infrastructure failure, not a task failure.

## Not claimed

- One instance. `move_to_pose` may fail for different reasons on different runs.
- The rate of mode C is unknown - 1 in 12 is a single observation.
- T08 remains `CALIBRATION_UNSUPPORTED`.