# A-prime executed: the fair A-prime-vs-B comparison on T14 (task-12)

**Auditor** gate-auditor · **Date** 2026-11-12 · **Task** task-12  
**Budget used** 16 Gazebo runs, **0 model calls**, one at a time under
`/tmp/evobot_sim.lock`, 0 orphans after every run.

---

## 0. The result

| metric | A-prime (rules) | B (deepseek-flash) |
| --- | --- | --- |
| planning_correct | **16/16** | **16/16** |
| execution_succeeded (1st attempt) | **9/16** | **11/16** |
| independent_evaluation_passed (1st attempt) | **13/16** | **14/16** |
| evaluation_passed (after recovery) | N/A — no recovery layer | **16/16** |
| **model calls (cost)** | **0** | **16** |

**The two arms produced byte-identical plans (16/16 identical stage poses, not merely
the same order).** Verified by direct comparison of `plan.json` between
`runs/<id>/` and the archived B run.

So the honest reading: **on T14, B's measurable planning value is zero.** A
deterministic 118-line regex planner reproduces the LLM's plan exactly, on all 16
instances, including the temporal ordering T14 was built to test. The two arms then
differ by **one instance** in evaluation (13 vs 14), in the *same* execution failure
mode — which is run-to-run variance, not a planning difference.

B's remaining advantage is **architectural, not intellectual**: B's pipeline includes a
recovery layer that rescued 2 failed first attempts (14/16 → 16/16). A-prime was run
one-shot with no recovery, so it stays at 13/16. That is a difference in the harness
around the planner, not in the planner.

---

## 1. An identical plan does not imply identical execution

This is the single most important caveat, and B's own numbers are the proof:

| arm | planned | executed 1st attempt | evaluated 1st attempt |
| --- | --- | --- | --- |
| B | **16/16** | **11/16** | **14/16** |
| A-prime | **16/16** | **9/16** | **13/16** |

Both arms plan perfectly and then lose 3–7 instances in the executor. The gap between
"planned" and "passes" is 5 instances for B and 7 for A-prime, **with identical
plans**.

### The executor's verdict and the world's state are different things

A-prime's 7 execution failures all carry `error_code 62`, detail
`native terminal/verification unconfirmed`. **Four of those 7 still evaluated as
passes** — the objects ended up in the correct bin, in the correct order, and the
frozen evaluator agreed. Same on B's side: 11 executed, 14 evaluated.

Concretely `HO-40348a081df6`: the executor reported error 62 with
`completed_stage_ids=[]`, and the ground truth captured from Gazebo shows
target_box_a at 58 mm and target_box_b at 48 mm from the zone centre, both inside the
60 mm radius. **The FSM said it failed; the world says it did not.**

This is the same separation task-4 found and it is why the four numbers are reported
separately. Anyone quoting only one of them is making a different claim.

---

## 2. Fairness: six conditions, all met

| # | condition | how it was satisfied |
| --- | --- | --- |
| 1 | same 16 T14 ids | the exact `HO-*` ids from `evobot_crosstype_20261111/runs_T14_ordered_pair/` |
| 2 | same observation | `build_aprime_plans.py` asserts A-prime's observation equals B's `observation_input.json`; **16/16** |
| 3 | same executor path | `benchmark/tools/run_composite_plan.py` → `RunComposite` action `run_composite`, served by `task_fsm_server.py:288-293` |
| 4 | same evaluator | `benchmark/evaluators/evaluate.py` v0.5.0, unmodified |
| 5 | four numbers, never folded | sections 0 and 1 |
| 6 | cost column | 0 vs 16 model calls |

**Condition 3 is the one that matters most for later readers.** B's 16 archived runs
genuinely went through `RunComposite` — their `task.out` carries
`run_id: "composite-8336b65a86ac4792"` and `completed_stage_ids`, which only
`_execute_composite` produces. This batch used that same path. **Do not re-run A-prime
through `pick_object`/`place_object` directly and call it comparable** — that is a
different executor and the comparison would be void.

### The plan conversion is shared, not re-implemented

`build_aprime_plans.py` calls the **same** `run_baseline_b.to_executor_plan()` that
produced B's `plan.json`, including the same `spread_destinations` de-overlap. Only
the planner differs. Byte-identical plans are the outcome, which is the strongest
possible evidence that condition 3 holds.

---

## 3. Two measurement traps, both avoided

Carried from the earlier B re-grade, where I hit the first and nearly hit the second:

1. **`observation.json` is the FINAL state; `observation_after1.json` is the FIRST
   attempt.** They are identical for 14 of B's runs and differ for the 2 resumed ones.
   Grading only the final state credits recovery to the first attempt.
2. **`recovery_decision.json` has two shapes**: flat `{'action': 'no_recovery'}` when
   the first attempt was clean, nested `{'decision': {'action': 'resume'}}` when it was
   not. Reading only the top-level key reports the 2 resumed runs as *unrecovered*.
   My first pass made exactly that error and I corrected it.

### A third trap I created and then caught

My first A-prime grading derived `move_sequence` from the executor's
`completed_stage_ids`, while B's came from `observe_from_run`'s `pick.jsonl` rule
(`outcome==0`, in order). **Different recorders for the two arms.** That manufactured a
difference not present in the world: A-prime scored 9/16 on evaluation instead of its
true 13/16, because an FSM verdict of "failed" produced an empty sequence even when
both objects had been placed correctly.

Fixed by building A-prime's observation with the **same**
`observe_from_run.build_observation()` that produced B's `observation.json`, from the
same `pick.jsonl` rule and the same `GZ_GROUND_TRUTH` capture. The corrected number is
13/16. The wrong number (9/16) is recorded here rather than deleted, because it is the
kind of error that would have made A-prime look worse than B for a measurement reason.

---

## 4. A-prime execution was briefly BLOCKED_INFRA — and why that was not an infra gap

An earlier attempt at this batch failed on every trial with `STACK_DOWN`. The cause was
**my own driver**, not the environment and not the Lead's concurrent launch:

`run_aprime_batch.sh` set `PYTHONPATH=$WT/src/flexcell/flexcell_skills`, which shadowed
the installed stack with the worktree's `flexcell_skills`. That version's
`task_fsm_server.py:44` imports `PushObject`, an action added to the worktree for T08
and **never built into `flexcell-p14-ws`**. Result: `task_fsm_server` died with
`ImportError: cannot import name 'PushObject'`, so `/run_composite` never appeared and
every trial timed out.

Fix: do not prepend the worktree's `flexcell_skills`. The installed stack is also the
fairness-correct choice, since B used `/home/ros/flexcell-p14`.

**Recorded because the distinction matters:** the run was blocked by a reproducible
local configuration error, not by a missing component. The earlier suspicion that the
`run_composite` action server did not exist was **wrong** — verified live: the action
is advertised 2 s after stack start, served by `/task_fsm_server`.

---

## 5. Invalid trials

**None.** 16/16 executed, 16/16 ground truth captured with `source: GZ_GROUND_TRUTH`,
0 orphans after every run. Every failure in the table is a real executor outcome
(`error_code 62`), not an infrastructure artefact.

---

## 6. What this does and does not establish

**Establishes:**

- A-prime executes. It is not a paper baseline.
- With identical plans, A-prime scores 13/16 at **zero model cost** against B's 14/16
  at 16 model calls. The one-instance difference is in the same failure mode both arms
  exhibit.
- **B has no measurable planning advantage on T14.** A 118-line regex parser matches it
  16/16 on plans.

**Does not establish:**

- Anything about other templates. T14 is one template family; T12/T13 were planned but
  not executed.
- That A-prime is "better". It is not: 13 vs 14 is within variance and B additionally
  has a recovery layer A-prime lacks.
- That the executor is reliable. It reports error 62 on runs whose world state is
  correct ~30% of the time, on **both** arms. That is a separate, live defect.

---

## 7. Reproducing

```
python3 setup/acceptance/evobot_p0_aprime_execution_20261112/build_aprime_plans.py   # offline
bash    setup/acceptance/evobot_p0_aprime_execution_20261112/run_aprime_batch.sh     # 16 runs, lock held
python3 setup/acceptance/evobot_p0_aprime_execution_20261112/grade_final.py          # symmetric grade
```

Artifacts: `runs/<id>/{plan,composite,ground_truth}.json` + `sim/skills/*.jsonl`,
`execution.tsv`, `grading/aprime_vs_b_final.json`.

No frozen file was modified: `rule_planner.py`, `run_baseline_a_prime.py`,
`run_baseline_b.py`, `run_composite_plan.py`, `evaluate.py`, `verify.py` and every task
spec are untouched.
