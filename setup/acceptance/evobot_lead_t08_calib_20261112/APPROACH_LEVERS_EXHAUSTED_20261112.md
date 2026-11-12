# Every external lever is now exhausted: the drag-back is ~0.06 m and does not care what the push does

Seed 3002, biased staging, `distance 0.040`, contact height 0.020. Only the staging **x** varied.

| staging x | push (best -x) | drag-back | net | min ee z | zone distance |
| --- | --- | --- | --- | --- | --- |
| 0.35 | -0.037 | +0.070 | +0.033 | 0.019 | 0.133 OUT |
| 0.30 | -0.0310 | **+0.0623** | +0.0313 | 0.0184 | 0.1313 OUT |
| 0.27 | **-0.0549** | **+0.0579** | +0.0030 | 0.0217 | 0.1030 OUT |

## The pattern

**The push varies with staging x - 0.031 to 0.055 - and the drag-back stays near 0.06.**
The two nearly cancel every time, and where the push grows the net falls, because the arm
ends up further past the box and drags it further back.

## The levers tested and what each gave

| lever | effect on the reversal | round |
| --- | --- | --- |
| staging y (lateral offset) | fixed seed 2000, **no effect on 3002** | 62-63 |
| `distance_m` 0.040 / 0.090 / 0.130 | no effect; return exceeds advance at 0.130 | 65 |
| staging x 0.35 / 0.30 / 0.27 | no effect; drag stays ~0.06 as push varies | 66 |
| `contact_height_m` | excluded arithmetically in an earlier round - reaching the fingers to
  the box needs the ee frame below the floor | earlier |

**All of these act on the approach. The drag happens on the way out.**

## What this establishes

The box is carried back by roughly **0.06 m** regardless of how it was approached or how far
it was pushed. No setting of the push command available at the interface can beat that,
because none of them changes what the gripper does **after** the push reaches its limit.

## The remaining legitimate option

Change the retreat itself. The arm must clear the box vertically before withdrawing in x.
`contracts/push.py` owns the sequence and is frozen. The routes inside `AUTHORITY_SCOPE.md`
section 1 are `contracts/push_recover.py`, recovery scheduling, and "interfaces required for
safe re-positioning - anything I must call to put the arm back on a legal contact side".

**Not attempted.** It needs its own paired test, and it is the first change in this line of
work that touches motion after the push rather than the approach to it.

## Not claimed

- Three runs here, one seed. Existence and non-improvement, not rates.
- The 0.06 figure is an observation across four runs, not a calibrated constant.
- T08 remains `CALIBRATION_UNSUPPORTED`.