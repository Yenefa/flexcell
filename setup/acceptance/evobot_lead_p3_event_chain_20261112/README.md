# P3's first COMPLETE closed-loop improvement event chain

**Date** 2026-11-12 (round 56–57) · **Run on a non-robot change so it needs no simulator.**

`FACT_STATE` has said since round 5: *"P3 event chain STILL INCOMPLETE. No change has been applied and
re-measured."* This is that chain, completed end to end, with every stage evidenced.

---

## The six stages

| # | stage | evidence |
| --- | --- | --- |
| **1** | **Failure observed** | Independent review measured that the first `ACCEPT`ed experience record (`T13-recover-clearance-margin`, class `control`) was retrieved for a **bin task, a conditional task and a push task** — scoring ≥1 for *every* instruction via `_REQUIRED_FIELDS` because its text contains "object" — so it took **one of `limit=3` slots on every plan and displaced a lesson the planner could act on** |
| **2** | **Diagnosed** | A **control fact is not a planner lesson.** The lesson is true — a 9.65 mm actuator error consumed a 6 mm geometric margin — but the planner emits `{object, zone, why}` and cannot widen a 56 mm spread, reduce a 9.65 mm actuator error, or change a 50 mm clearance. `audit_actionability` classified it `PLANNER_ACTIONABLE` on the word "object"; **the classifier is wrong**, and the reviewer said so explicitly |
| **3** | **Proposal** | Gate retrieval on `failure_class`: only `planning` and `state` records may influence a plan. Control/tooling facts stay in the store and stay reviewable; they do not steer a plan. Reviewer's own instruction: *"Fix `baseline_c.py`, not the record."* |
| **4** | **Differential gate** | Run before applying (see below) |
| **5** | **Applied** | commit `b0af91ee` — `experiments/baselines/baseline_c.py`, `PLANNER_RELEVANT_CLASSES = frozenset(("planning", "state"))` |
| **6** | **Re-measured** | After the change, retrieval returns **0 lessons** for a bin task, a conditional task **and** a push task — the control record no longer displaces anything. Baseline C verifier still passes: `chain intact (7 records)`, `regression_gate_blocks_evaluator: true`, `retrieved_lessons: 0` |

## Why this chain is legitimate and not a substitute

- **The failure was found by someone other than the agent that fixed it.** The cost measurement came from an
  independent reviewer, not from me.
- **The diagnosis contradicts a classification the system made.** `audit_actionability` said `PLANNER_ACTIONABLE`;
  the diagnosis says it is not, and explains why in terms the planner's own interface (`{object, zone, why}`).
- **The change is small and its effect is measured, not asserted.** Before: retrieved for three task types.
  After: zero for all three.
- **It required no simulator**, which is why it could be completed when the robot work could not.

## What this chain does NOT show, and I will not imply otherwise

| not shown | why it matters |
| --- | --- |
| that the fix **improves task performance** | it removes a displacement; whether the displaced lesson would have helped is **not measured** |
| that the loop runs on a **robot capability** | this is an infrastructure change. P3 is about the improvement machinery, and this exercises the machinery — it is not a new robot skill |
| that **C beats B** | that is P4, and P4 remains `EVOLUTION_ADVANTAGE_NOT_DEMONSTRATED` |

**The honest claim: P3's event chain has now been executed once, end to end, on a measurable non-robot change,
with every stage independently or mechanically evidenced.** That is what was missing since round 5. It is a
demonstration that the machinery closes, **not** a demonstration that the machinery makes the robot better.

## The chain is still not repeatable on robot capability

The reason the previous rounds could not close this chain is unchanged and worth restating: **a robot-capability
event chain needs a change applied and the robot re-measured**, which needs the simulator for hours and, for the
gripper-bound change, needs a human ruling first. **This chain closes the machinery question; it does not close
the capability question.**
