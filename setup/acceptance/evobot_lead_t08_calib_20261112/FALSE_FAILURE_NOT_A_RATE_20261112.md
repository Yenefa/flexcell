# The false failure does NOT generalise: 1 of 3 runs moved the box into the window

Round 58 reported a confirmed false failure on `T08-push-seed3001`. One example is not a rate,
so this round repeated the identical procedure on three seeds.

## Results, single staged push, identical parameters

| seed | displacement (m) | cosine | contact | in 0.03-0.15 window |
| --- | --- | --- | --- | --- |
| 3001 | **0.1112** | +0.9979 | yes | **yes** |
| 3002 | **0.0000** | 0.0000 | **no** | no |
| 2000 | 0.0155 | +0.9920 | yes | **no — below the 0.03 floor** |

**One of three runs produced a task-satisfying displacement.**

## What this changes

The round 58 false failure stands as a real event - box 0.01725 m from the zone centre, both
clauses passing, rejected on 3.2 mrad of aperture. **But it cannot be presented as a rate.**
On two of three seeds the run fails before the gripper gate is reached:

- seed 3002 never made contact at all (`contact=False`, zero movement).
- seed 2000 made contact and pushed only 0.0155 m, under the 0.03 floor.

## The dominant defect is displacement, not the gripper gate

Across these three runs displacement ranges **0.0000 to 0.1112 m** under one fixed parameter
set. This is the same picture the objective already records: *same-condition achieved ranges
0.0-73.1 mm across nine runs*. Nothing here contradicts that, and the staging candidate does
not fix it.

**The gripper gate is a real false rejection, but it is the LAST obstacle, not the first.**
Improving it changes nothing until displacement is repeatable enough to reach it.

## Honest accounting

- Round 58's false failure: **one confirmed instance, not a rate.**
- Succeeding runs: **1 of 3** on these seeds with the staged candidate.
- What I have that survives: the evidence chain (gates reached 8/10, terminal passing on a
  satisfying run), the mechanism for the gripper rejection, and the two-push bug that was
  silently corrupting every grade before it.

## What this does not license

- It does not license calling the candidate a success at any rate.
- It does not license calling the gripper gate the main defect.
- It does not change T08 status: still `CALIBRATION_UNSUPPORTED`.