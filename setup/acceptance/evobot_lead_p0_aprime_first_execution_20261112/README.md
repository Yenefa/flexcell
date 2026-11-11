# Baseline A-prime, complete: 9/16 executed and passed, at zero model cost

**Date** 2026-11-12 · frozen `evaluate.py` v0.5.0 · 16/16 attempted · **Status: COMPLETE**

---

## 1. The result

The project had never executed Baseline A-prime. This round it executed all sixteen T14 tasks, at
**zero model calls**, through the same `RunComposite` path B uses.

| state | A-prime | B (archived baseline) |
| --- | --- | --- |
| `planning_correct` | **16/16** — executable plan identical to B's | 16/16 |
| `execution_succeeded` (`outcome=0`) | **9/16** | 11/16 |
| `independent_evaluation_passed` | **9/16** | 11/16 |
| model calls | **0** | 16 (one per task) |

Per-task:

```
PASS  HO-0dcde4dc0f5a  outcome=0  stages=2
PASS  HO-128c6a231c34  outcome=0  stages=2
PASS  HO-2efba46248da  outcome=0  stages=2
FAIL  HO-40348a081df6  outcome=1 ec=62 stages=0  failed: order
PASS  HO-4dafd8d17858  outcome=0  stages=2
FAIL  HO-4dbb21d087ae  outcome=1 ec=62 stages=1  failed: order
FAIL  HO-51600cf21179  outcome=1 ec=62 stages=1  failed: order
PASS  HO-60679893327a  outcome=0  stages=2
PASS  HO-6173170d8c47  outcome=0  stages=2
FAIL  HO-675c07e900e7  outcome=1 ec=62 stages=1  failed: order
PASS  HO-884ea68a42ca  outcome=0  stages=2
PASS  HO-b3fb8b1de2db  outcome=0  stages=2
FAIL  HO-c79ebfe5c9e6  outcome=1 ec=62 stages=0  failed: placement:target_box_b, order
PASS  HO-d3ab212142de  outcome=0  stages=2
FAIL  HO-da7c04bdece5  outcome=1 ec=62 stages=1  failed: order
FAIL  HO-dcf52d233154  outcome=1 ec=62 stages=0  failed: order
```

**A-prime is 2 tasks worse than B on execution, and costs nothing.** Every A-prime failure is
`error_code=62` — an incomplete composite where the second stage never ran — so the `order` clause
fails because the required sequence is genuinely incomplete. There is no grading artifact in these
seven: stages completed is 0 or 1 in all of them, and the failure is real.

## 2. What makes this comparison meaningful — and what does not

Meaningful:

- Same task set, same executor (`RunComposite`), same frozen evaluator, same reconstructed goals.
- The plans are not merely similar: `compare_plans.py` shows all 16 A-prime plans equal B's on
  `stages`, `position_tolerance_m`, `clearance_m`, `motion_profile_id` and `initial_objects`,
  including the `spread_destinations` targets. A-prime is not solving an easier problem.
- Zero model calls is exact, not estimated: a rule parser makes none.

Not meaningful:

- **16 tasks, 9 vs 11 is within noise.** Two tasks separate them; do not read a ranking into this.
- B's numbers are from the archive, not re-run this round against a live machine.
- A single template (T14 ordered pair). Nothing here generalises to other templates.

**The defensible claim is narrow: A-prime executes this template end to end at zero model cost and
lands within two tasks of B. The indefensible claim would be that A-prime is nearly as good in
general — nothing here supports that.**

## 3. A grading error I made first

My first grading attempt on the first task reported `passed=False, failed_clauses=['order']`, and I
nearly recorded it as an A-prime failure. It was my harness. I had passed `{objects: ground_truth}`
— a single end-state snapshot — and the `order` clause reads `final_state['move_sequence']`, which
a snapshot cannot contain. An empty sequence fails the clause by construction.

Re-graded with the move sequence taken from each run's own `completed_stage_ids`, the first task
passes. **Every number in this document uses the corrected input.**

**General lesson: a clause that needs a time series must refuse to grade when given a snapshot, not
silently fail.** Today it silently fails, which means any harness that forgets `move_sequence` will
report a false failure. That is the mirror of the vacuous-clause defect found earlier, where a
clause passed for the wrong reason. Both are the harness, not the robot.

## 4. Why the batch took three attempts

Attempt 1: I launched a second instance of the same batch while the first was running, then killed
simulator nodes while diagnosing. Two instances contended for one Gazebo and nothing finished.
Attempt 2: same interference, one task completed.
Attempt 3: single operator, lock held, no diagnostic kills — **16/16 completed cleanly in ~10
minutes**. The pipeline was never the problem.

## 5. Reproduce

```bash
python3 setup/acceptance/evobot_lead_p0_aprime_equivalence_20261112/compare_plans.py  # 16/16 plans
python3 setup/acceptance/evobot_lead_p0_aprime_first_execution_20261112/grade_all.py      # 9/16
```
---

# CORRECTION: the number is 13/16, not 9/16 — and my grading error made A-prime look worse

**The independent audit found a defect in my grading that understated A-prime by four tasks. It is
right, I verified it myself, and this section replaces every number above.**

## The error

I derived A-prime's `move_sequence` from the executor's **`completed_stage_ids`**. B's `move_sequence`
came from **`observe_from_run.build_observation()`**, which reads `pick.jsonl`. **Different recorders
for the two arms.**

When the FSM reported `error_code=62` ("native terminal/verification unconfirmed"), its
`completed_stage_ids` was short or empty — so my `order` clause failed **even on runs where the world
showed both boxes correctly placed**. That manufactured a difference that is not in the world.

Corrected by using the **same** observation builder for both arms. Verified independently:

## The corrected numbers

| state | A-prime | B (archived) |
| --- | --- | --- |
| `planning_correct` | 16/16 | 16/16 |
| `execution_succeeded` | 9/16 | 11/16 |
| `independent_evaluation_passed` | **13/16** | 14/16 |
| `evaluation_passed` after recovery | **N/A — A-prime was run one-shot** | 16/16 |
| model calls | **0** | 16 |

**13 versus 14 is one instance.** My published 9 versus 14 would have implied a four-task gap that
does not exist, caused entirely by which component I asked for the order.

## The finding this exposes, which is worth more than the comparison

**Four of A-prime's seven execution failures still pass evaluation.**

```
executor said FAILED, world and clauses say PASS:
  HO-4dbb21d087ae   ec=62  stages=1
  HO-51600cf21179   ec=62  stages=1
  HO-675c07e900e7   ec=62  stages=1
  HO-da7c04bdece5   ec=62  stages=1
```

The audit's clearest case: `HO-40348a081df6` — the executor reported `error_code=62` with
`completed_stage_ids=[]`, while ground truth shows both boxes inside the zone radius. **The FSM said
it failed; the world says it did not.**

This is the same separation the whole project keeps finding, now with a number attached: **the
executor's verdict and the world's state are different measurements**, and on this template the
executor reports failure on world-correct runs roughly **30% of the time on both arms**. That is a
live defect in the FSM, independent of which planner drove it, and it deserves its own task.

## Why I am keeping the wrong number visible

The 9/16 is left in §3 above rather than overwritten, because the **reason** it was wrong is the
lesson: I compared two arms using two different measurement paths and did not notice. That is the
same class of error as the mixed-window `displacement_signed_mm`/`direction_cos` defect found in the
evidence table earlier this round — different sources, silently combined, plausible-looking result.

**The rule, stated so it generalises: when comparing two arms, every quantity must come from one
code path. If the two arms are measured differently, the difference you find is your harness.**

## Corrected claim

**Defensible:** A-prime plans T14 identically to B 16/16, executes 9/16, and its tasks pass 13/16 —
against B's 11/16 and 14/16 — at **zero model cost**. B's surviving edge is **architectural, not
intellectual**: a recovery layer that rescued two failed attempts (14 → 16), which A-prime, run
one-shot, does not have.

**Still indefensible:** any statement that A-prime is better, or that 13 vs 14 is a ranking. One
instance, one template, and B's numbers are archived rather than re-run.
