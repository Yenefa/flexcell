# P0 has no A′ baseline: the rule planner matches zero of the 72 tasks

**Date** 2026-11-12 · **Found by** the Lead · **Status: CONFIRMED, offline, no simulator**
**Effect: the P0 fair-baseline comparison the Master Goal requires does not exist, and never has.**

---

## 1. The observation

Every A′ plan artifact on disk records a refusal:

```
a_prime.json files under evobot_t05* : 20
  planned = true  :  0
  refused         : 20   (all: "no rule matches this instruction")
```

Rather than treat 20 archived refusals as the whole story, I re-ran the planner over **all 72 train
specs** offline. It refuses **72 of 72**:

| template | planned | refused |
| --- | --- | --- |
| T01_multi_object_sorting | 0 | 12 |
| T02_exclusion | 0 | 12 |
| T03_ordered | 0 | 12 |
| T04_duplicates | 0 | 12 |
| T05_relay | 0 | 12 |
| T06_revisit | 0 | 12 |
| **total** | **0** | **72** |

Single refusal note in every case: `no rule matched - declined`.

## 2. The cause — the rules were written for templates that do not exist

`runtime/planner/rule_planner.py` contains seven regexes. Matching them against a real instruction
(`T01-train-seed1000`: *"Put the red block in the right bin and the blue block in the left bin."*):

| rule pattern (abridged) | matches? |
| --- | --- |
| `the (\w+) block must be put there first` | no |
| `in the (\w+) bin` | **yes** — but it is a *sub*-pattern of the first rule, not a rule of its own |
| `then the (\w+) block` | no |
| `if the (\w+) block is closer to the (left|right) bin` | no |
| `put the (\w+) block in the (\w+) bin,\s*then move it to the (\w+) bin` | no |
| `put both blocks in the (\w+) bin` | no |

Every rule is anchored on phrasings that appear in **T12** ("...then move it to...") and **T14**
("...must be put there first..."). A census of every task spec on disk:

```
T01 18   T02 18   T03 18   T04 18   T05 18   T06 18   T08 6
T12: absent      T14: absent
```

**So the rule planner implements two templates that do not exist in this benchmark, and implements
none of the six that do.** The one pattern that does match (`in the (\w+) bin`) is a fragment consumed
inside the T14 rule, so it can never fire on its own.

## 3. Why this is worse than a low score

A′ is the **deterministic, zero-model-cost** arm of P0. Its stated purpose, in its own docstring, is:

> "if it matches B, B's measurable value on these templates is zero"

That inference requires A′ to **produce a plan**. With 0/72, A′ produces no plan, executes nothing, and
therefore cannot be compared to B on any template. Every P0 statement that reads "A′ vs B" is
comparing **B against an arm that never acted**. Any conclusion of the form "B is better than A′" is
currently vacuous, and any conclusion of the form "A′ suffices" is unsupported.

This is the same defect class as the round-1 findings about the oracle mislabel and the vacuous
placement clause: **an artifact that looks like a measurement and is not one.**

## 4. What must NOT be concluded

| Tempting claim | Status |
| --- | --- |
| "A′ fails, so B is necessary" | **FORBIDDEN** — A′ never ran. This would be a false capability claim for B |
| "A′ is broken, so B is fine" | **FORBIDDEN** — says nothing about B |
| "P0 shows a baseline gap" | **FORBIDDEN** — there is no A′ measurement at all |
| "the rule planner is worthless" | not established either — it may work on T12/T14, which are simply not in this benchmark |

## 5. The fix is small, and it is a real experiment

Six instruction forms exist. Six rules would cover them, and the observation already carries
everything needed (`objects` with colours and positions, `zones` with positions and radii):

| template | instruction | rule needs |
| --- | --- | --- |
| T01 | "red → right bin, blue → left bin" | colour → side map |
| T02 | "clear into right bin except blue, which stays" | exclusion set |
| T03 | "into right bin in this order: red, then blue" | ordered list |
| T04 | "ignore colours; FURTHER from base → right, nearer → left" | distance from base |
| T05 | "blue → left bin, passing through right first" | relay waypoint |
| T06 | "blue → left, then move on to right; only final counts" | two-step, final position |

That is a **bounded, testable piece of work with a hard success criterion: 72/72 plans produced, each
graded against `expected_goal` by the frozen evaluator.** Until then, P0 has no A′ arm and the
Master Goal's "fair baselines A/A′/B with real Gazebo execution" is **NOT_RUN**, not "failed".

## 6. Reproduce

```bash
python3 setup/acceptance/evobot_lead_p0_aprime_vacuity_20261112/scan_aprime_coverage.py
```

Runs offline against the task specs; no simulator, no model calls. The script refuses (exit 1) if it
finds zero specs, so a path error cannot be mistaken for a clean result.

---

## 7. Is A-prime at least *blind* to the answer? Yes — with one latent hole

A-prime being vacuous (§1–2) and A-prime being honest are separate questions, and the second one
matters independently: if the rules could see the answer, then fixing them would produce an oracle,
not a baseline. That is exactly the defect that sank Baseline A.

`check_aprime_blindness.py` tests it structurally rather than trusting the docstring:

| Check | Result |
| --- | --- |
| `reduce_to_public()` strips `expected_goal`, `constraints`, `template_id`, `random_seed`, verdict keys | **PASS** — reduced keys are exactly `evaluator_version, execution_budget, instruction, objects, split, task_id, zones` |
| Corrupting `expected_goal` cannot change the plan | **PASS** — four corruptions (`{'x':1}`, `None`, `'GARBAGE'`, a plausible fake goal) all leave the plan byte-identical |
| The caller applies the reducer **unconditionally** | **CONDITIONAL — latent hole** |

`run_baseline_a_prime.py:40-41` reads:

```python
task_public = (po.reduce_to_public(raw_task)
               if 'expected_goal' in raw_task else raw_task)
```

If a spec ever lacks `expected_goal`, the **raw** task is used unfiltered — carrying `constraints`
and `template_id`. `template_id` is precisely the key that would let a rule planner special-case a
template instead of reading the instruction.

**It is harmless today:** 0 of 114 specs lack `expected_goal`. And applying the reducer
unconditionally would change nothing — I checked, the resulting observation is identical.

**Not fixed here**, because it is a P0 entry point shared with other baselines and the fix belongs
with the rule work (task-10), which touches the same file. Recorded rather than silently patched.

## 8. Reproduce

```bash
python3 setup/acceptance/evobot_lead_p0_aprime_vacuity_20261112/scan_aprime_coverage.py
python3 setup/acceptance/evobot_lead_p0_aprime_vacuity_20261112/check_aprime_blindness.py
```

Both offline, no simulator, no model calls. The coverage scanner refuses on zero specs; the
blindness checker refuses if the sample spec lacks `expected_goal`, since the test would otherwise
be vacuous itself.
