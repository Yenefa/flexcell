# Benchmark defect: 16 of 72 training instances have a placement clause already satisfied at t=0

**Date** 2026-11-12 · **Found by** the T04 diagnosis lane, **independently reproduced by the Lead**
**Severity** high — it does not break any run, but it makes part of the benchmark's pass count free

---

## 1. The defect in one sentence

A placement clause is scored `passed` when the object is **within `zone.radius` of the zone centre**.
For 16 of the 72 training instances the target object **starts inside its destination zone**, so that
clause is satisfied before the robot moves and the instance scores a pass on work that was never done.

## 2. Reproduction (Lead, independent of the lane's script)

For every `benchmark/tasks/train/*.json`: compute `hypot(start_x - zone_x, start_y - zone_y)` for each
`expected_goal.placement` entry and compare with that zone's `radius`.

```
train instances: 72
fully vacuous (all placement clauses satisfied at t0): 4
partially vacuous (>=1 free clause): 12
```

| Task | Class | Free clause | distance | radius | margin |
| --- | --- | --- | --- | --- | --- |
| T04-train-seed1000 … seed1011 (**all 12**) | PARTIAL | `target_box_a` → `zone_2` | 0.05831 | 0.06 | **1.69 mm** |
| T05-train-seed1001 | **VACUOUS** | `target_box_a` → `zone_2` | 0.05831 | 0.06 | 1.69 mm |
| T05-train-seed1007 | **VACUOUS** | same | 0.05831 | 0.06 | 1.69 mm |
| T05-train-seed1009 | **VACUOUS** | same | 0.05831 | 0.06 | 1.69 mm |
| T05-train-seed1010 | **VACUOUS** | same | 0.05831 | 0.06 | 1.69 mm |

Every one of the 16 is the **same** free clause: `target_box_a` spawns at `[0.22, 0.0]`, and `zone_2`
is centred at `[0.25, 0.05]` with radius 0.06, giving a 58.31 mm separation — 1.69 mm inside the radius.

**The 1.69 mm margin is the whole story.** The clause is not merely close: it is satisfied by 1.7 mm,
on a task whose entire point is to move that object. And the object never moves in the passing runs —
`gt_after` is byte-identical to the initial pose for `target_box_a` in T04-train-seed1000.

## 3. What this does and does not invalidate

| Claim | Effect |
| --- | --- |
| A-v2 = 71/72 executed and graded | **UNAFFECTED** — the runs happened, the evaluator ran |
| A-v2's 71/72 is a measure of *robot manipulation* | **OVERSTATED** — in 16 instances at least one clause required no manipulation, and in 4 the goal is fully vacuous |
| "T04-train-seed1000 PASS" | **REAL BUT WEAKER THAN IT LOOKS** — one of its two clauses was free; the run genuinely moved `target_box_b`, so it is not a false pass, but the instance is not a two-clause test |
| T05-train-seed1001's known **failure** | **UNAFFECTED and still meaningful** — it failed *despite* a free clause, which makes the failure stronger, not weaker |
| B's 9/9 | **UNAFFECTED as an execution result**, but 3 of the 9 executed instances are T04 (free clause) — see §4 |
| T08 | **UNAFFECTED** — push tasks have no `placement` clause; they are judged by displacement/direction/zone and are not in this set |

## 4. The part that matters for the P0 comparison

The B-vs-oracle paired execution used **9 instances: T01×3, T02×1, T04×3, T06×2**.
**Three of those nine (all the T04s) contain a free clause.** So one third of the paired execution
sample is partly pre-satisfied. The 9/9 result is not wrong, but the effective number of
*independently-earned* clauses in that sample is lower than nine instances suggests.

## 5. Why this is a research-integrity issue and not just a task-design wart

The benchmark's job is to distinguish a system that can manipulate from one that cannot. A clause that
is satisfied at t=0 cannot do that. Worse, the failure is **silent**: nothing in the verdict records
that a clause was already true, so every downstream reader — including the round's own capability
report — inherits an inflated impression of what was demonstrated.

This is the same class as the two other provenance defects found this round (the oracle mislabelled as
A′, and the three modules called A′): **a document or a schema asserting something that nothing
verifies.**

## 6. What is NOT claimed here

- **No threshold was changed and none should be.** The zone radius 0.06 is a frozen evaluator
  parameter; editing it would be exactly the "adjust the acceptance rule to manufacture success"
  failure the mission forbids.
- **No existing result is deleted or re-labelled.** A-v2 stays 71/72; B stays 9/9.
- This is **not** evidence that any pass was fraudulent. In T04 the other clause did require real work
  and it was really done.

## 7. Recommended disposition (needs a decision, not an edit)

| Option | Consequence |
| --- | --- |
| **A. Report the vacuity alongside the number** (minimum, zero risk) | Every document quoting a pass count states how many instances had a free clause. No result changes. |
| **B. Add a `t0_satisfied` flag to the verdict schema** | Machine-visible; lets any reader filter. Requires an evaluator version bump (v0.6.0, already planned for the evidence work). |
| **C. Regenerate T04/T05 specs so no clause is satisfied at t=0** | Correct long-term, but it invalidates the frozen 72-instance set and every result measured on it — a P0-level decision requiring human approval. |

**Recommendation: A now, B when v0.6.0 is cut, C only with explicit approval.** A is free and closes the
honesty gap immediately; C destroys comparability with every number this project has produced.

## 8. A note on how this script failed the first time (kept deliberately)

The first version of `scan_vacuity.py` computed the repo root by hopping a fixed number of parent
directories. Run from its final location it resolved to the wrong directory, found no task files, and
printed:

```
train instances: 0
fully vacuous (every placement clause satisfied at t0): 0
partially vacuous (>=1 free clause): 0
```

**Exit code 0. No error. A clean-looking result that meant nothing.**

That is precisely the failure class the Skill Curator's round-2 report identified as recurring in this
project (its metric M8: "empty output read as success"). It is recorded here rather than quietly fixed
because it is the same shape as the defect this document is about: *a number that nothing checks*.
The fix was to walk up until `benchmark/tasks/train` exists and to **refuse loudly** if it does not, and
to refuse if zero specs were found. A scanner that can silently scan nothing is not a scanner.

## 9. Reproduce

```bash
python3 setup/acceptance/evobot_lead_benchmark_vacuity_20261112/scan_vacuity.py
```

Reads only `benchmark/tasks/train/*.json`. No simulator, no model calls.
