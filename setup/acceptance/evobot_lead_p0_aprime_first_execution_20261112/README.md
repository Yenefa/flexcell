# A-prime's first execution in project history: it passed, and it cost zero model calls

**Date** 2026-11-12 · **n = 1 of 16** · frozen `evaluate.py` v0.5.0 · **Status: CONFIRMED, n=1**

---

## 1. What happened

The project had **never executed Baseline A-prime** — not once. It had only ever produced plans.
The batch approved this round ran one task to completion before operator interference
(mine — see `evobot_lead_p0_composite_retraction_20261112/`) terminated the remaining fifteen.

That one task is a real result, and it is the first of its kind:

| field | value |
| --- | --- |
| task | `HO-0dcde4dc0f5a` (T14 ordered pair) |
| composite result | `outcome = 0`, `error_code = 0` |
| `run_id` | `composite-c32a5b7b75c341ef` |
| completed stage ids | `['target_box_b-0', 'target_box_a-1']` |
| detail | "all native stages and fresh joint conditions confirmed" |
| wall time | 36 s |
| model calls | **0** |

## 2. The graded result — all clauses pass

Graded with the frozen evaluator against the spec, using the auditor's reconstruction of
`expected_goal` (validated 16/16 against the archive's own recorded answer, since the real seal is
root-only and I chose not to break it for a grading convenience):

```
placement:target_box_a   ok=True
placement:target_box_b   ok=True
order                    ok=True

passed            : True
terminal_passed   : True
failed_clauses    : []
```

Ground truth: `target_box_a` at (0.3047, 0.0492), `target_box_b` at (0.2106, 0.0470) — both inside
`zone_2` at (0.25, 0.05) r = 0.06, and in the required order (blue first, then red).

## 3. The four states, separated

| state | value |
| --- | --- |
| `planning_correct` | **16/16** (all 16 plans match B's executable plan exactly) |
| `execution_succeeded` | **1/1 attempted** (the other 15 were never attempted) |
| `independent_evaluation_passed` | **1/1** — all clauses |
| `agent_claimed_success` | **false** — A-prime claims nothing; it is a rule parser |

Note the shape: 16 plans, 1 execution, 1 pass. **Those are three different denominators and must
never be collapsed.** "A-prime passes 1/1" and "A-prime plans 16/16" are both true and neither
implies the other.

## 4. A grading error I made first, and how it was caught

My **first** grading attempt reported `passed=False, failed_clauses=['order']` — and I nearly recorded
that as an A-prime failure. It was not. I had graded against `{objects: ground_truth}`, a single
end-state snapshot, and the `order` clause reads `final_state['move_sequence']` — an event sequence
that a snapshot does not contain. An empty sequence fails the clause by construction.

Re-graded with the move sequence taken from the composite's own `completed_stage_ids`:

```
completed_stage_ids : ['target_box_b-0', 'target_box_a-1']
derived move_sequence: ['target_box_b', 'target_box_a']
required order       : ['target_box_b', 'target_box_a']  ->  match
```

**This is the sixth premise error of the round and the most dangerous kind**: a grading harness
that silently reports failure when it is given insufficient input. It is the mirror of the
vacuous-clause finding — there, a clause passed for the wrong reason; here, a clause failed for the
wrong reason. Both are the harness, not the robot.

**The general lesson, stated so it can be applied elsewhere: a clause that needs a time series must
refuse to grade when given a snapshot, not silently fail.** Currently it silently fails.

## 5. What this does and does not establish

| Claim | Status |
| --- | --- |
| A-prime has executed at least one task and passed it | **CONFIRMED, n=1** |
| A-prime's execution is at zero model cost | **CONFIRMED** |
| A-prime's executor plan equals B's on all 16 | **CONFIRMED** at plan level |
| A-prime passes T14 generally | **NOT ESTABLISHED** — 1 of 16 executed, and n=1 supports no rate |
| A-prime beats or matches B on execution | **NOT ESTABLISHED** — B's rate is 11/16 first attempt; comparing 1/1 to 16 runs is meaningless |

**The honest summary: the pipeline works end to end for A-prime, at zero cost, and the question
"what is A-prime's pass rate on T14?" now has a method and one data point instead of no method.**

## 6. The remaining work is now purely operational

Fifteen tasks remain. Nothing technical blocks them: the server exists (`task_fsm_server.py:289`),
the plans are built and committed, the executor path is the same one B used, and one task has now
run cleanly in 36 s. What went wrong was **two operators contending for one simulator**. The fix is
process, not code: one lane, one operator, lock held, no second instance, and no diagnostic kills
against a live run.

## 7. Reproduce

```bash
# the plan equivalence (16/16), from committed artifacts, no simulator:
python3 setup/acceptance/evobot_lead_p0_aprime_equivalence_20261112/compare_plans.py
# the graded execution (1/1):
python3 setup/acceptance/evobot_lead_p0_aprime_first_execution_20261112/grade_first_execution.py
```
