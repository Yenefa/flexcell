# CRITICAL: T08 is not failing on motion. It is failing because no trajectory evidence is supplied.

**Date** 2026-11-12 (round 34) · **This overturns the round-17 conclusion that the arm cannot do T08.**

---

## 1. The verdict, unedited

Trial 1 of the paired run — recorded as `terminal_passed=False`, `failed=['push:target_box_a']`:

```
displacement_m      : 0.14965     min 0.03   max 0.15    PASS
vertical_m          : 0.0         max 0.02               PASS
direction_cosine    : 0.99999     min 0.9                PASS
inside_zone         : true        distance 0.04965, radius 0.06   PASS
reason  : "no trajectory for this object: end state alone cannot prove it was pushed
           rather than carried"
trajectory_required : true
```

```
evidence.failure_reason : "no evidence bundle was supplied; a push cannot be confirmed
                           from terminal geometry alone"
evidence.evidence_status: INCOMPLETE_OR_INVALID_EVIDENCE
```

**Every geometric sub-clause passed.** The box moved 149.65 mm, stayed at the same height, travelled at
cosine 0.99999, and finished **inside** the target zone. **That is a correct push.**

The trial was rejected for **one** reason: **no trajectory evidence bundle was supplied**.

## 2. Why — one line of plumbing

The runner grades with:

```python
evaluate.py  task.json  gt_after.json        # two arguments
```

**The trajectory is never passed.** `evaluate.py` v0.5.0 requires it — `trajectory_required: true` — because
T08's fail-closed design is specifically built so that *"end state alone cannot prove it was pushed rather than
carried"*, which is the pick-carry-place defence the Master Goal demands. **The defence is working exactly as
designed; the system is not feeding it.**

## 3. What this does to my earlier conclusions

| claim I made | status |
| --- | --- |
| **"the arm repeats to ±3.44 mm against a 2.5 mm cliff; this configuration cannot do this task"** (r17) | **THE MEASUREMENT IS REAL, THE INFERENCE IS WRONG.** The physical push succeeded on trial 1. The arm can push 149.65 mm into the zone. My ±3.44 mm figure is a pose-repeatability fact, not a task-capability limit |
| "no request-field value can fix T08" (r17) | **WRONG in reasoning** — the lever was never motion, so motion was never the constraint |
| "displacement is not the binding constraint" (r27–33) | **CORRECT**, and now explained: the binding constraint is **evidence plumbing**, not any geometry clause |
| "T08 skill-level 0/26" | **TRUE of the graded result, MISLEADING as a capability statement.** All 26 failed the same way — on missing evidence |
| recovery shows no benefit (r33) | **premature.** Recovery cannot help; every attempt was rejected for the same non-motion reason |

**The height sweep, the ±3.44 mm figure, and the 'cliff' are all measurements of a variable that was never the
deciding one.** Rounds 17–19 built a careful quantitative story about the wrong quantity.

## 4. What has to be established next

1. **Does the runner ever pass a trajectory bundle?** If not, every T08 number in this repository — including
   the pilot's 4/5 and the 2/5 baseline — was produced without the required evidence, and **must be re-graded**.
2. **How does the pilot's 4/5 exist at all?** If the pilot passed 4 of 5 with the same two-argument grading,
   something differed between then and now. That difference is the next thing to find.
3. **Only then** does the physical question (repeatability, cliff) become relevant again.

## 5. What I am not claiming

**I am not claiming T08 passes.** 0 of 26 graded passes stand. I am claiming the **stated cause** was wrong: the
clause evidence shows a correct physical push rejected for absent trajectory evidence. Whether supplying that
evidence would produce passes is **untested**, and the pilot's 4/5 is now **suspect rather than refuted**, which
is a different and less comfortable position than round 33 recorded.

**This must be resolved before any T08 number in this repo is cited again.**