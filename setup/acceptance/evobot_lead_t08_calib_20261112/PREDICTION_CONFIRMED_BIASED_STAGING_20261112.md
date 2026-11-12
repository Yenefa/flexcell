# THE PREDICTION HELD: offsetting the staging point removed the reversal on seed 2000

The previous round stated a falsifiable prediction:

> if both-finger contact causes the reversal, then moving the staging point's y to match the
> box's y - so the gripper arrives off-axis on every run - should make the reversal disappear.

**It was tested on the exact seed that reversed, and it held.**

## Same seed, same task, one parameter changed

`T08-push-seed2000`, box at (0.2200, 0.0000), zone at (0.12, 0.0) r=0.06.

| | staging y = 0.00 (original) | staging y = 0.07 (offset) |
| --- | --- | --- |
| box x | 0.2200 -> **0.2462** | 0.2200 -> **0.1290** |
| direction | **+x, REVERSED** | **-x, correct** |
| displacement | 0.0155 m | **0.0910 m** |
| reported cosine | +0.9920 (sign wrong) | **+0.9999** |
| contact | yes | yes |
| zone | outside | **0.0091 m from centre, radius 0.06 - INSIDE** |

The offset `+0.07` was not tuned to this seed. It reproduces the lateral offset that seed
3001 happened to have - box y -0.07 against an ee y of 0.00 - which was the run that pushed
correctly.

## What this establishes

1. **The reversal is caused by contact geometry, not by control.** Changing only where the arm
   waits before the push changes the direction of travel while the commanded push is identical.
2. **Both-finger contact is the discriminator.** seed 2000 originally had 383 left-finger and
   451 right-finger contacts; the offset removes the second finger's access.
3. **The mechanism is actionable inside the granted scope.** The change is a staging
   coordinate passed to `move_to_pose`. `contracts/push.py` is untouched, no threshold moved,
   no TaskSpec edited, no evaluator modified.

## What this does NOT establish

- **One run.** This is a prediction confirmed once, not a rate. The previous round's own
  lesson applies: a single result does not generalise.
- **The offset is not derived.** 0.07 was copied from an observed geometry, not computed from
  the finger span or box size. A principled value may differ.
- **It does not fix displacement variance.** seed 3002 still executed nothing at all; this
  change does not address a push that never runs.
- **No capability level is claimed.** This run has not been through the frozen evaluator with
  a complete evidence bundle, and T08 remains `CALIBRATION_UNSUPPORTED`.

## The next test

Repeat on seeds 3001, 3002 and 2000 with the same offset, and compare against the un-offset
results already recorded. Until that runs, this is one confirmed prediction.