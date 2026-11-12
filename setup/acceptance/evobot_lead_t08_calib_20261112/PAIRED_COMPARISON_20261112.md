# Paired comparison: biased staging fixes 1 of 3 seeds, and seed 3002 is unaffected

Critical-path item 4: paired original-vs-candidate on identical task, seed and validator.
Six runs, three seeds, two staging configurations, everything else identical.

## Results

| seed | config | staging y | box dx | displacement | zone distance | direction | in zone |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2000 | original | 0.00 | **+0.0000** | 0.0000 | 0.1000 | never moved | no |
| 2000 | **biased** | 0.07 | **-0.1188** | **0.1190** | **0.0197** | correct | **YES** |
| 3001 | original | 0.00 | -0.0887 | 0.0911 | 0.0233 | correct | **YES** |
| 3001 | biased | 0.00 | -0.0908 | 0.0928 | 0.0216 | correct | **YES** |
| 3002 | original | 0.00 | **+0.0297** | 0.0298 | 0.1297 | **REVERSED** | no |
| 3002 | biased | 0.09 | **+0.0328** | 0.0332 | 0.1329 | **REVERSED** | no |

**Original: 1 of 3 in zone. Biased: 2 of 3 in zone.**

Note that seed 3001's `biased` staging y also came out 0.00 - its box is at y -0.07, so
-0.07 + 0.07 = 0.00 - meaning that cell is the same configuration as its original and is a
repeat, not an independent condition. It reproduced (0.0911 vs 0.0928), which is a
reproducibility datum, not a second success.

## What this supports

Seed 2000 is the clean case: identical task, identical push command, staging y 0.00 vs 0.07,
and the outcome changes from **no movement at all** to **0.1190 m into the zone**. That is one
seed, and it agrees with the prediction from the previous round.

## What this contradicts

**Seed 3002 reverses in BOTH configurations, and the displacement is essentially unchanged**
(+0.0297 original, +0.0328 biased). The offset does nothing for it.

This is important because it breaks the simple story. The offset on 3002 was 0.07, the same
magnitude that worked on 3001, and the box still went the wrong way. Whatever drives 3002's
reversal is **not** the lateral offset that drives 2000's.

## So the mechanism is narrower than the previous round said

The previous round concluded that both-finger contact causes the reversal and that offsetting
the staging point removes it. **Seed 3002 falsifies the general form:** it reverses with the
same offset applied.

The safe statement is: **for seed 2000, the reversal was caused by gripper-box alignment and
the offset fixed it.** Generalising to 'alignment causes reversals' is not supported.

## Honest position

- 6 runs, 3 seeds, 2 conditions - far too few to estimate a rate.
- One seed changed behaviour; one was unchanged; one reproduced itself.
- T08 remains `CALIBRATION_UNSUPPORTED`. No capability level is claimed.
- Seed 3002 has failed in every configuration tried so far and is the clearest open case.