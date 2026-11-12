# The retreat lift does NOT improve the success count: 2 of 3 against 2 of 3

Round 68 reported a single paired run where the lift took the drag from +0.0596 to 0.0000 and
put seed 3002 in the zone. That was one seed. This round ran the same paired design on three.

## Results

| seed | config | push | drag | net | zone distance | in zone |
| --- | --- | --- | --- | --- | --- | --- |
| 2000 | lift 0.0 | -0.0116 | **+0.0490** | +0.0374 | 0.1374 | no |
| 2000 | **lift 0.08** | -0.0886 | **+0.0004** | -0.0882 | **0.0118** | **yes** |
| 3001 | **lift 0.0** | -0.0941 | **+0.0010** | -0.0932 | **0.0157** | **yes** |
| 3001 | lift 0.08 | -0.0307 | **+0.0439** | +0.0132 | 0.1132 | **no** |
| 3002 | **lift 0.0** | -0.1230 | +0.0015 | -0.1215 | **0.0286** | **yes** |
| 3002 | **lift 0.08** | -0.1119 | +0.0000 | -0.1119 | **0.0184** | **yes** |

**Baseline 2 of 3. Lift 2 of 3.** No net gain.

## What went wrong with the round-68 story

**Seed 3001 got WORSE**: in the zone at baseline (0.0157), out of it with the lift (0.1132).
The lift fixed 2000 and broke 3001.

**Seed 3002 passed at baseline this time** (0.0286) when in round 68 the same baseline
configuration put it at 0.1290 - out of the zone. Same seed, same parameters, opposite verdict.

**That second point is the more important one.** It means a single run of this task is not a
reliable measurement, and any conclusion drawn from one pair - including round 68's - was drawn
from noise.

## What actually holds

The drag-back is real and the lift removes it where it occurs. Look at the drag column:
baseline rows show +0.0490 and +0.0439 at the two failures, and +0.0010 / +0.0015 at the two
passes. **Drag above ~0.04 correlates with failure in all six runs.**

What does not hold is that removing the drag makes the run succeed. The lift removed drag on
seed 3001 and the run failed anyway, because **the push itself collapsed** - from -0.0941 to
-0.0307. The lift changed how the push proceeds, and that effect is larger than its benefit.

## Honest position

- The lift is a real, mechanically-correct fix to a real defect, and it is not sufficient.
- Round 68's conclusion was over-stated: one paired run, and it has now failed to replicate.
- The run-to-run variance of this task, at fixed parameters, is large enough that single runs
  cannot distinguish a fix from noise. **Any future claim here needs repeats per cell.**
- T08 remains `CALIBRATION_UNSUPPORTED`.

## Not attempted

Repeating each cell 3-5 times to get a rate. That is what the next stage requires before any
claim can be made about the lift, and before the evaluator work is worth re-running.