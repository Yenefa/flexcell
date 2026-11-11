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
