# CORRECTION: `outcome 1` from move_to_pose means FAILED - and I have been reading it as success

`MoveToPose.action:37-40`:

```
uint8 OUTCOME_SUCCEEDED     = 0
uint8 OUTCOME_FAILED        = 1
uint8 OUTCOME_CANCELED      = 2
uint8 OUTCOME_STATE_UNKNOWN = 3
```

**`OUTCOME_FAILED` is 1.**

Since round 62 I have been logging `staging move to (0.35, 0.07, 0.03) -> 1` and reporting it as
a staging move that took effect. **It means the move reported failure.**

## Why the results still moved the box

`outcome FAILED` from `move_to_pose` does **not** mean the arm did not move. It means the move did
not reach its target. A run that logged `-> 1` still showed `link5_x_z` at **-0.3366**, so the arm
had moved substantially - it simply did not arrive within tolerance.

**So two different things were being conflated, by me:**

- `outcome 1` = "did not arrive" - common, and the arm still moves
- `ee_descent 0.0001` = "did not move at all" - the actual no-op

## What this corrects

1. **The staging move has never reported success in any run I logged.** Every `staging ... -> 1`
   line in rounds 62-70 is a failed arrival, not a successful one. The staging effect that the
   earlier rounds measured - the pitch change - is real, but it came from a move that reported
   failure.
2. **The candidate's `stage_ok` guard was checking the right thing** (the pitch after the move),
   not the outcome. That was accidentally correct; `stage_outcome == '1'` would have rejected
   every run.
3. **Mode C is still distinct.** In that run BOTH moves reported FAILED *and* ee never descended.
   The difference is the descent, not the outcome code.

## The lesson that keeps recurring

Three times this session a silent-failure pattern was diagnosed and the check was added in one
place: round 53 (staging), round 60 (seed 3002 zero run), round 70 (mode C). **Each time I read an
outcome field without first confirming its encoding.** This round is the fourth instance of the
same root error, and it is mine, not the code's.

**Rule to carry forward: read the enum before reading the value.**

## Not claimed

- Does not overturn the measured results: the pitch changes, the drag-backs, the three modes are
  all observed from pose series and remain as recorded.
- Does not explain why move_to_pose misses its target so consistently. **That is now a sharper
  question than it was: if every staging move reports failure but still produces the intended
  pitch change, the arrival tolerance or the IK is worth looking at.**
- T08 remains `CALIBRATION_UNSUPPORTED`.