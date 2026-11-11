# Independent verification of the "Baseline A-prime plans 0 of 72" claim

**Auditor** gate-auditor (independent validation lane) · **Date** 2026-11-12  
**Task** task-11 · **Subject** `runtime/planner/rule_planner.py` vs the benchmark corpus  
**Verdict** **PARTIAL — the number is CONFIRMED, the characterisation is REFUTED**

I wrote my own census from scratch (`scan_independent.py`) and did not import the Lead's
scanner. We agree on the number. We disagree on what it means, and the disagreement
matters: the headline "A-prime is vacuous" is not supported by the evidence, and a
narrower, true statement is available.

---

## 1. CONFIRMED — A-prime plans 0 of 114 specs (independent reproduction)

`scan_independent.py`, my own enumeration, calling the real planner through
`public_observation`:

| template | n | planned |
| --- | --- | --- |
| T01_multi_object_sorting | 18 | 0 |
| T02_exclusion | 18 | 0 |
| T03_ordered | 18 | 0 |
| T04_duplicates | 18 | 0 |
| T05_relay | 18 | 0 |
| T06_revisit | 18 | 0 |
| T08_push_manipulation | 6 | 0 |
| **TOTAL** | **114** | **0** |

114, not 72 — the corpus also contains T08. The Lead's 72 counts only the six T01–T06
train templates (18 each); the wider corpus is 114 and the answer is still 0.

Of the 11 distinct instructions in the corpus, exactly **one fragment** matches anything:
`in the (\w+) bin`. That is a sub-pattern consumed *inside* the T13/T14 rules and is not
a standalone rule — confirmed by reading the source, where the only `return moves`
statements sit inside four complete rules. The Lead's statement of this is correct.

## 2. REFUTED — "rules written for templates that do not exist here"

**This is the part that is wrong, and it changes the finding.**

T12, T13 and T14 are **not absent from the repo**. They are implemented as first-class
generators in `benchmark/generators/unseen_tasks.py:67-153`:

```python
TEMPLATES = {
    "T12_triple_revisit": t12_triple_revisit,
    "T13_geometric_conditional": t13_geometric_conditional,
    "T14_ordered_pair": t14_ordered_pair,
}
```

They are referenced by five build scripts, two test modules, the held-out sealer, and a
`runtime/planner/rule_planner_pre_t14.py` that exists *specifically* as the pre-T14
lineage. They are simply **not in `benchmark/tasks/`**, which is what the Lead's census
enumerated.

### The decisive test: do the rules work on their own templates?

I generated 12 instances of each and ran the real planner
(`test_rules_on_their_own_templates.py`, `test_correctness_on_templates.py`):

| template | n | planned | **correct** |
| --- | --- | --- | --- |
| T12_triple_revisit | 12 | 12 | **12** |
| T13_geometric_conditional | 12 | 12 | **12** |
| T14_ordered_pair | 12 | 12 | **12** |
| **TOTAL** | **36** | **36** | **36** |

**A-prime is 36/36 correct on the templates it targets.** It is not a vacuous baseline.
It is a working baseline pointed at templates the benchmark split does not contain.

Control that the rule set is a real lineage, not a fluke: `rule_planner_pre_t14.py`
(T12+T13 only, T14 branch removed) scores 12/12, 12/12, **5/12** — it fails T14 exactly
where the T14 branch is missing, and its 5 "successes" are the order-luck cases the
project already documented. The full rule set fixes precisely those.

### T14 was not just generated — it was EXECUTED

`setup/acceptance/evobot_crosstype_20261111/runs_T14_ordered_pair/` contains **16 real
Gazebo runs**. Re-running the live planner on the first one's actual observation:

```
instruction: "Put both blocks in the left bin. The blue block must be put there FIRST, then the red block..."
live rule_planner -> 2 moves, note='T14 order parsed'
  [{'object': 'target_box_b', 'zone': 'zone_2', ...}, {'object': 'target_box_a', 'zone': 'zone_2', ...}]
```

So A-prime has a recorded history of acting on T14 — just not inside `benchmark/tasks/`.

## 3. Attacks on the claim — all four failed to find a hidden path

`attack_claim.py`:

| attack | result |
| --- | --- |
| A1 are the rules live, or dead code? | **4/4 synthetic probes fire.** Rules are functional. |
| A2 does `run_baseline_a_prime.py` succeed where a direct call fails? | **No.** Exit 1, no `plan.json`, writes `result.json` with `planned:false`. Agrees with the direct call. |
| A3 alternate entry point / fallback / wrapper? | **No.** `plan(observation)` is the only function; no `try/except`; the final statement is the bare refusal. |
| A4 does observation shape change the outcome? | **No.** Reversed objects/zones, extra skills, no budget, empty objects, single zone, uppercased instruction — all 0 moves. |

**The 0/114 is a genuine phrasing mismatch, not dead code and not a wiring bug.**

## 4. Archived artifacts cross-check — 21/21 agree

Every archived `a_prime*.json` in the repo (21 files) compared against a live re-run on
the same task id: **21 agree, 0 disagree.** All 21 are `planned:false` with a refusal
string, and all 21 are T05 instances — the archive is consistent with the census.

## 5. Where I think the Lead is wrong, and the narrower true statement

**"A-prime is vacuous" is the wrong characterisation.** Vacuous means the arm cannot
act, or its output is empty of content. Neither is true: the arm acts correctly on
36/36 instances of the templates it was built for, and it declined honestly (rather than
guessing) on the 114 it cannot parse.

The accurate statement is narrower and more useful:

> **A-prime is correct for T12/T13/T14 and the benchmark's task split contains none of
> them.** P0's A-prime-vs-B comparison is therefore NOT_RUN — not because the baseline
> is vacuous, but because the two arms were pointed at different template families: B at
> T01–T06, A-prime at T12–T14. The baseline is real; the *pairing* is the defect.

That distinction is not cosmetic. It changes the remedy:

| if "vacuous" | if "split mismatch" (the truth) |
| --- | --- |
| rewrite the rule planner | add T12/T13/T14 specs to the split, or run A-prime on them |
| baseline is worthless | baseline is fine; the experiment was mis-paired |
| P0 needs a new baseline | P0 needs a matching corpus — the arm already works |

**The consequence the Lead states is still correct:** every "A-prime vs B" statement
compares B against an arm that produced no plan on those tasks, and P0's fair-baseline
comparison is **NOT_RUN, not failed**. I confirm that.

## 6. One latent hole confirmed (Lead's own note)

`run_baseline_a_prime.py:40-41` applies `reduce_to_public` only when the spec has
`expected_goal`. A spec lacking that key passes through raw, carrying `template_id`.
I checked: **0 of 114 specs lack it**, so it is harmless today. It belongs with the fix,
not in a panic — the Lead's framing is right.

## 7. Verdict

| Lead claim | my verdict |
| --- | --- |
| A-prime plans 0 of 72 train specs | **CONFIRMED** (I measure 0 of 114 on the wider corpus) |
| the seven regexes anchor on T12/T14 phrasings | **CONFIRMED** |
| T12/T14 exist nowhere in the repo | **REFUTED** — generators, tests, build scripts, a pre-T14 lineage module, and 16 executed T14 runs |
| the one matching pattern is a fragment, cannot fire alone | **CONFIRMED** |
| every "A-prime vs B" compares B to an arm that never acted | **CONFIRMED** |
| P0 fair-baseline comparison is NOT_RUN, not failed | **CONFIRMED** |
| **"A-prime is vacuous"** | **REFUTED** — it is 36/36 correct on its target templates |

**Net: the number is right, the headline is wrong.** Use the narrower statement.

---

## 8. Reproducing

```
python3 setup/acceptance/evobot_p0_aprime_independent_20261112/scan_independent.py
python3 setup/acceptance/evobot_p0_aprime_independent_20261112/attack_claim.py
python3 setup/acceptance/evobot_p0_aprime_independent_20261112/test_rules_on_their_own_templates.py
python3 setup/acceptance/evobot_p0_aprime_independent_20261112/test_correctness_on_templates.py
```

Artifacts: `census/coverage_rows.tsv` (114 rows).

Nothing was fixed or edited: `rule_planner.py`, `run_baseline_a_prime.py` and every
task spec are untouched.
