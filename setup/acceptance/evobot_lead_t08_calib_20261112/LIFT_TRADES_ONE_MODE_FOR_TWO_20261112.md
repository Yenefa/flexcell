# The lift trades one failure mode for two: drag-back goes to zero, no-push and no-op appear

The push-executed guard from round 73 applied retroactively to the twelve runs of round 70.

## Classification

| config | n | OK | A drag-back | B no-push | C no-op |
| --- | --- | --- | --- | --- | --- |
| **lift 0.0** | 6 | 4 | **2** | 0 | 0 |
| **lift 0.08** | 6 | 4 | **0** | **1** | **1** |

Per run:

```
2000/0.08 r1  OK         push -0.0884  drag +0.0000  zone 0.0121
2000/0.08 r2  B_no-push  push -0.0051  drag +0.0070  zone 0.1019
2000/0.08 r3  OK         push -0.1008  drag +0.0001  zone 0.0015
2000/0.0  r1  A_dragback push -0.0310  drag +0.0596  zone 0.1288
2000/0.0  r2  OK         push -0.1196  drag +0.0000  zone 0.0197
2000/0.0  r3  OK         push -0.1024  drag +0.0000  zone 0.0030
3001/0.08 r1  OK         push -0.1062  drag +0.0000  zone 0.0182
3001/0.08 r2  OK         push -0.1069  drag +0.0002  zone 0.0134
3001/0.08 r3  NO-OP      push +0.0000  drag +0.0000  zone 0.1000
3001/0.0  r1  A_dragback push -0.0456  drag +0.0782  zone 0.1327
3001/0.0  r2  OK         push -0.0949  drag +0.0030  zone 0.0206
3001/0.0  r3  OK         push -0.1096  drag +0.0008  zone 0.0205
```

## What the split shows

**Both configurations pass 4 of 6.** But the *way* they fail is completely different:

- **Baseline failures are exclusively mode A.** Both failures carry drag of +0.0596 and +0.0782,
  and both boxes end behind their start.
- **Lift failures are never mode A.** Drag on those runs is +0.0070 and +0.0000. The lift works
  exactly as designed - and those two runs fail for two other reasons instead.

## The honest reading

The retreat lift does what it says. It removes a real defect. **And it does not raise the
success rate, because the task has at least three independent ways to fail and removing one
lets the others through.**

This is why round 68's single paired run looked like a fix: it happened to sample an OK run
under lift, and an A run under baseline, which is exactly what the six-and-six split predicts
would happen about a third of the time.

## What this does not tell us

- **Whether the modes are independent.** 12 runs cannot show whether B and C are caused by the
  lift or merely unmasked by it.
- **The base rates.** With 2/1/1 failures across 12 runs, the split is a shape, not a
  distribution.
- **Anything about unseen instances.** All twelve runs are on seeds 2000 and 3001.

## Consequence for the next stage

A rate measured without per-mode attribution is not interpretable on this task. Any future
comparison has to report **which mode** failed, not just how many.

The guard added in round 73 is what makes that possible: it separates C from A and B
automatically, and A from B is separable from the push and drag values.