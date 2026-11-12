# `max_lift` predicts `terminal_passed` 18 out of 18 - the hypothesis holds exactly

Round 86 identified the no-grasp lift bound as the term that was failing. This round tests it as
a predictor rather than an explanation.

## The prediction

> if `max_lift_m <= 0.005` then the push clause passes, and `terminal_passed` is True

## The result

| run | terminal | max_lift | grip delta |
| --- | --- | --- | --- |
| fix_2000_0.08_1 | False | 0.00706 | 0.0022 |
| fix_2000_0.08_2 | False | 0.00530 | 0.0041 |
| fix_2000_0.08_3 | False | 0.00564 | 0.0000 |
| fix_2000_0.0_1 | **True** | **0.00219** | 0.0060 |
| fix_2000_0.0_2 | **True** | **0.00254** | 0.0040 |
| fix_2000_0.0_3 | False | 0.00730 | 0.0020 |
| fix_3001_0.08_1 | False | 0.00723 | 0.0133 |
| fix_3001_0.08_2 | False | 0.00723 | 0.0000 |
| fix_3001_0.08_3 | False | 0.00719 | 0.0041 |
| fix_3001_0.0_1 | False | 0.00712 | 0.0132 |
| fix_3001_0.0_2 | False | 0.00720 | 0.0145 |
| fix_3001_0.0_3 | False | 0.00720 | 0.0000 |
| ho_3000_1 | **True** | **0.00361** | 0.0068 |
| ho_3000_2 | False | 0.00725 | 0.0000 |
| ho_3000_3 | **True** | **0.00092** | 0.0098 |
| ho_3002_1 | **True** | **0.00074** | 0.0077 |
| ho_3002_2 | **True** | **0.00339** | 0.0136 |
| ho_3002_3 | **True** | **0.00240** | 0.0044 |

**18 out of 18.** The seven runs under 5 mm pass; the eleven over 5 mm fail. No exceptions, and
the two groups do not overlap - the highest passing value is 0.00361 and the lowest failing value
is 0.00530.

## The two blockers are independent

`grip delta` does not separate the groups at all. Runs with `terminal=True` carry grip deltas of
0.0060, 0.0040, 0.0068, 0.0098, 0.0077, 0.0136 and 0.0044 - every one of them above the
0.0020 rad limit. **So `gripper` rejects all 18, independently of `max_lift`, which rejects 11.**

```
max_lift > 0.005   -> 11 runs fail the push clause
gripper > 0.0020   -> all 18 fail the gripper gate
both under their limits -> 0 runs
```

## What this establishes

1. **The push clause is not failing on task performance.** Displacement, direction, zone and
   vertical are all satisfied on the 11 - only the 5 mm lift bound is not.
2. **The lift is 5.3 to 7.3 mm** on the failures against a 118 mm horizontal push. That is a
   ratio of about 17:1, not a carry.
3. **Two independent sensor-threshold rejections** now stand between this task and certification:
   a lift bound and an aperture bound, both sized for deliberate manipulation and both triggered
   by passively-induced motion.

## What I am not claiming

- **Not Independently Verified. 0 of 18.** The evaluator rejected every run.
- **Not that the bounds are wrong.** Both correctly reject a grasp-carry. The question is whether
  a 5 mm / 0.0020 rad pair can ever admit a push by fingers that ride on the box's top face.
- **No threshold was changed.** Both are in the frozen evaluator.
- **This does not make T08 a success.** It makes the reason for `CALIBRATION_UNSUPPORTED`
  precisely measurable, which is what the objective asked for.