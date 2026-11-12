# RETREAT-VS-TRANSIT: settled. The retreat path carries the box back

The objective records this as unresolved:

> retreat-vs-transit not yet settled because no end-effector pose series has been captured

A pose series has now been captured, and the answer is **retreat**.

## Seed 3002, biased staging, 337 samples across one push

| t | ee x | box x | what is happening |
| --- | --- | --- | --- |
| 0.36 | 0.2860 | 0.1900 | start |
| 2.72 | 0.2362 | 0.1895 | descending |
| 3.94 | 0.1868 | **0.1578** | pushing -x, box moving correctly |
| 5.21 | 0.1682 | **0.1544** | still correct |
| 6.53 | 0.1405 | **0.1542** | arm ahead of the box |
| 7.86 | **0.1129** | **0.1530** | furthest point; box at its best, **-0.037 from start** |
| 9.20 | **0.1804** | 0.1761 | **arm retreating, past the box** |
| 10.57 | 0.2365 | **0.2228** | **box dragged to +0.033** |

**The push works.** By t=7.86 the box has moved 0.037 m in the commanded -x direction, more
than the 0.030 minimum. Then the arm withdraws from x=0.1129 to x=0.2365, and the box follows
it back to +0.033 - past where it started.

The same pattern, weaker, in the original configuration: box reaches 0.1779 at t=3.42 (a
correct -0.012) before being carried back to 0.2184.

## Why this settles the question

`ee_travel_m` for this run is 0.1100 while the net displacement is 0.0332. The arm moves 0.11,
the box ends 0.033 from where it began, and the peak correct excursion was 0.037 in the other
direction. **The box's path is not monotonic; it goes the right way and then comes back.**

An earlier observation in this session - `arm_travel 0.358 against net 0.046`, a ratio of
7.79x - now has a mechanism rather than being a curiosity.

## The mechanism

The fingers sit 44.3 mm behind the end-effector frame and ride above the box top at the
approach pitch. On the way in, one finger presses a side face and pushes correctly. On the way
out, the same finger - or the gripper body - is on the far side of the box, and withdrawing
drags it back.

**This is consistent with the established geometry and explains why a correct push can end
with a reversed net displacement.** It is not proven: proving it needs the retreat path
sampled more densely than 337 points, and ideally a direct force/contact reading during
withdrawal.

## The consequence for the whole task

**A push that succeeds can be nullified by its own retreat.** The recovery loop is not the only
source of backward motion; the plain T08 push produces it whenever the retreat crosses the box.

This also explains why seed 3001 succeeds and seed 3002 does not, with similar offsets: the
question is not whether the approach is offset, but whether the **withdrawal path** clears the
box.

## Not claimed

- One run at each configuration, for one seed. Existence proof, not a rate.
- The finger-geometry explanation is inferred, not measured during the retreat.
- No fix is proposed. The obvious candidate - retreat vertically before withdrawing in x -
  would be a change to the push/recovery path and needs its own paired test.