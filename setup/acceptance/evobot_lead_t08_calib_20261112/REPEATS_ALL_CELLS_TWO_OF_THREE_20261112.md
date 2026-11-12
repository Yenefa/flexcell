# Repeats settle it: all four cells are 2/3, and the lift only changes WHICH failure happens

Two seeds, two configurations, three repeats each. Twelve runs.

## Results

| cell | in zone | per-run | failure's drag | failure's push |
| --- | --- | --- | --- | --- |
| seed 2000, lift 0.0 | **2/3** | OUT, IN, IN | +0.0596 | -0.0310 |
| seed 2000, lift 0.08 | **2/3** | IN, OUT, IN | +0.0070 | **-0.0051** |
| seed 3001, lift 0.0 | **2/3** | OUT, IN, IN | +0.0782 | -0.0456 |
| seed 3001, lift 0.08 | **2/3** | IN, IN, OUT | +0.0000 | **+0.0000** |

**Every cell is 2 of 3.** The lift changes the success count by nothing.

## What the lift actually does

Look at the drag on the runs that failed:

- baseline failures: **+0.0596** and **+0.0782** - the drag-back
- lift failures: **+0.0070** and **+0.0000** - no meaningful drag

**The lift genuinely removes the drag-back.** That part of the round-68 finding reproduces:
when the lift is on, the return is gone.

**And the runs still fail at the same rate**, because a second failure mode takes over: the
push itself does not happen. The lift failures have push values of -0.0051 and +0.0000 - the arm
never moved the box. Only 1 of 12 runs shows a large push together with a large drag, so the
drag was never the dominant reason this task fails.

## What this means for the rounds before it

- **Round 68 was wrong to call this a fix.** One paired run where drag went to zero and the box
  landed in the zone - which the repeats show is the 2-in-3 outcome that happens anyway.
- **Round 69 was right to retract it**, and now has the numbers.
- **The retreat lift is a correct repair of a real defect that is not rate-limiting.** Worth
  keeping; not worth claiming as progress on the task.

## The finding that is actually load-bearing

**T08 push, at fixed parameters, succeeds about two times in three, and the failures come from
two independent causes:** a horizontal retreat that drags the box back, and a push that never
gets going.

This is the first rate measurement in this session with repeats behind it, and it is consistent
with the objective's own recorded observation of `0.0-73.1 mm` achieved displacement across nine
runs - the spread is the two failure modes, not measurement noise around a stable mean.

## Not claimed

- n=3 per cell. That is enough to see that four cells agree at 2/3 and not enough to put a
  confidence interval on it.
- The two failure modes are distinguished by their signatures, not by a controlled experiment
  that induces each one.
- T08 remains `CALIBRATION_UNSUPPORTED`. No capability level is claimed.