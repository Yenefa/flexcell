# P0 on T14: A-prime's executor plan is IDENTICAL to B's on 16/16, at zero model cost

**Date** 2026-11-12 · **Measured by** the Lead from the in-flight A-prime batch · **n = 16 frozen T14 instances**
**Status: CONFIRMED at the plan level. Execution is still running.**

---

## 1. Why this is the comparison P0 needed

P0 requires fair baselines A / A-prime / B under identical inputs. Until now that comparison did not
exist, for two separate reasons:

1. A-prime plans **0 of 114** specs in `benchmark/tasks/` — because the split contains T01–T06 and
   A-prime's rules target T12/T13/T14 (see `evobot_lead_p0_aprime_vacuity_20261112/`).
2. The 16 archived T14 runs under `evobot_crosstype_20261111/` are **arm B**, not A-prime
   (`requested_model = deepseek-flash` in every `agent_reply.json`, zero `a_prime` artifacts). So
   the project had **no A-prime execution at all**.

The audit is now running A-prime through the same executor path on the same 16 instances. This
document records what is already measurable from those runs' **plans**, before any execution
result exists.

## 2. The measurement

Comparing the **executor-relevant content** of each plan — `stages`, `position_tolerance_m`,
`clearance_m`, `motion_profile_id`, `initial_objects` — between A-prime's fresh plan and B's
archived plan, for the same task id:

| | count |
| --- | --- |
| **identical** | **16** |
| different | 0 |
| missing | 0 |

Not merely the same *order* — the same **destinations**, including the `spread_destinations`
post-processing that places the two blocks at distinct points inside the bin:

```
HO-0dcde4dc0f5a  both arms: target_box_b -> [0.205, 0.05, 0.0175]  spread_offset -0.045
                           target_box_a -> [0.295, 0.05, 0.0175]  spread_offset +0.045
HO-128c6a231c34  both arms: target_box_a -> [0.075, -0.15, 0.0175]
                           target_box_b -> [0.165, -0.15, 0.0175]
```

This matters because an earlier audit pass compared only the **rule planner's** raw output to B's
archived plan and found 0/16 identical — the difference being precisely that B applies
`spread_destinations` afterwards. Once A-prime is put through the **same** executor plan builder, the
difference disappears entirely. The two arms converge on the same executable plan.

## 3. What this establishes

| Claim | Status |
| --- | --- |
| On T14, A-prime produces the same executable plan as B | **CONFIRMED, 16/16** |
| A-prime's cost | **0 model calls**; B's is 16 |
| B's measurable planning value on T14 | **ZERO** — it adds nothing over a rule parser on this template family |
| A-prime executes and passes | **NOT YET MEASURED** — batch in flight |

**The third row is the substantive P0 result.** On T14, a deterministic rule parser at zero cost
reproduces the LLM's plan exactly. Whatever B contributes on these templates, it is not the plan.

## 4. What this does NOT establish, and the trap it would be easy to fall into

**Planning equivalence is not task equivalence.** B's own record on these 16 instances shows the
gap is real:

| B's numbers (audited) | |
| --- | --- |
| planning_correct | 16/16 |
| execution_succeeded, first attempt | **11/16** |
| independent_evaluation_passed, first attempt | **14/16** |
| evaluation_passed, after recovery | 16/16 |

Four different numbers from one batch of runs. So even with an **identical plan**, A-prime's
execution and evaluation numbers are open questions — the executor may treat the two arms
differently, and B's 11/16 shows that a correct plan frequently does not survive execution.

**A-prime could match B on all four numbers (B's planning value is zero), or beat it, or lose to it
(if something about the B path makes execution more robust). All three are live. Reporting
"A-prime matches B" without the execution numbers would be exactly the conflation this project
keeps finding.**

## 5. Honest limits

- **Plan-level only.** No A-prime execution result exists at the time of writing.
- **One template family (T14), n = 16.** Nothing here says A-prime would match B on T01–T06, where
  A-prime has no rules at all.
- **B was not re-run.** Its numbers are the archived ones, re-graded. Same evaluator, same specs,
  but not a fresh execution under today's conditions.
- The comparison is of **executor plans**, not of the planners' internal decisions. A-prime's rule
  output and B's model output are different objects; what is identical is what gets executed.

## 6. Reproduce

```bash
python3 setup/acceptance/evobot_lead_p0_aprime_equivalence_20261112/compare_plans.py
```

Compares the in-flight A-prime batch's `plan.json` against the archived B `plan.json` for the same
task id, on the executor-relevant keys. Refuses if either side is missing, so an empty comparison
cannot look like agreement.
