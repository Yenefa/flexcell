# Independent verification of the "A' column is the ORACLE" provenance claim

**Auditor** gate-auditor (independent validation lane) - **Date** 2026-11-12  
**Subject** `setup/acceptance/evobot_p0_aprime_mislabel_20261112/README.md`  
**Verdict** **CONFIRMED, with one material correction** - see section 4

I was asked to verify or refute the Lead's finding, not to accept it. Method: re-derived
every claim from the repository, ran both planners, and searched for a counter-artifact
that would make the finding wrong.

---

## 1. Is there any other artifact that really is A's plan? - **NO**

Searched all of `setup/acceptance/**`, `ci-public-window/**`, `experiments/**` for
`a_prime*` artifacts: **21 files**. All 21 are of the form

```
{"task_id": ..., "arm": "A_prime_rules", "planned": false,
 "refusal": "no rule matches this instruction"}
```

They are *refusals*, not plans - and they come from the **generic** planner
(`runtime/planner/rule_planner.py`, imported by `run_baseline_a_prime.py:29`), which
declines every T01-T06 instruction. They cover only T05-train-seed1000..1005; the overlap
with the 17 instances in the paired table is **3 of 17**.

So there is **no archived real-A plan** for the paired instances. The Lead's finding
stands: the column labelled A' has no real-A counterpart anywhere in the repo.

## 2. Reproduced the byte-identical claim - **CONFIRMED, and stronger than claimed**

The Lead reproduced it for 2 instances. I reproduced it for **all 72**:

```
for each of the 72 training specs:
  python3 experiments/baselines/build_composite_plan.py <spec> /tmp/rebuild_<task>.json
  compare to ci-public-window/evidence/baseline_a_v2_gated_20261111/<task>/plan.json
-> 72 / 72 byte-identical (sha256 equal)
```

`build_composite_plan.py:44` calls `sd.spread(ba.plan_from_spec(spec))`, and
`baseline_a_composite.py:26-27` reads `spec["expected_goal"]`. Confirmed by source and by
output. The archived "A'" directory is the **oracle** builder's output.

## 3. The real A' disagrees - **CONFIRMED**

Ran `runtime/planner/rule_planner_t01_t06.py` (the planner `evobot_p0_paired.sh:67`
declares as A') on the public observation:

| instance | real A' (`rule_planner_t01_t06`) | archived "A'" (oracle) | B |
| --- | --- | --- | --- |
| T06-train-seed1000 | zone_2 -> zone_1 (2 hops) | zone_1 only (1 hop) | zone_2 -> zone_1 (2 hops) |
| T05-train-seed1000 | zone_1 -> zone_2 (2 hops) | zone_1 -> zone_2 | zone_1 -> zone_2 |
| T01-train-seed1000 | 2 moves | 2 moves | 2 moves |

On T06 the archived "A'" matches the **oracle** and disagrees with the **real A'**, exactly
as the Lead reported. Note the real A' agrees with **B** on T06, which inverts the
document's narrative ("A' skips the relay, B follows the instruction literally").

## 4. CORRECTION to the Lead's section 4 - the 72/72 claim is **NOT** unaffected

The mislabel README section 4 states:

> "A' scores 72/72 at plan level on T01-T06" | **UNAFFECTED** - that number comes from
> `benchmark/rule_saturation_t01_t06.py` -> `rule_planner_t01_t06.py`, a different and
> correctly-labelled path

The path attribution is right, but **"unaffected" is wrong**, because there are **two
different "A'" planners in this repo** and the documents conflate them:

| consumer | planner module | T01 result | T06 result |
| --- | --- | --- | --- |
| `benchmark/rule_saturation_t01_t06.py:23` | `rule_planner_t01_t06` | 2 moves, correct | zone_2->zone_1, correct |
| `runtime/planner/run_baseline_a_prime.py:29` | `rule_planner` (generic) | **declines** | **declines** |
| `ci-public-window/scripts/evobot_p0_paired.sh:67` | `rule_planner_t01_t06` | 2 moves | zone_2->zone_1 |

Consequences:

1. The **72/72** number is real and reproducible (I re-ran it: 72/72 plan-correct), and it
   *is* the correct A' planner. That part of the Lead's section 4 is right.
2. But **A' has never been executed in Gazebo.** The 72/72 is `PLAN-LAYER ONLY` by the
   script's own banner. The mislabel README section 7 correctly proposes this as future work.
3. The claim in `BASELINE_CORRECTION.md:36` ("A' (no LLM) solves T01, T02, T04") refers to
   `baseline_a_prime_rules.py` - a **third** rule implementation with a different rule set
   (`BIN_WORD = {"right": "zone_1", "left": "zone_2"}`). It is neither of the two above.
   **Three distinct artifacts all called "A'"**. That is the actual provenance defect, and
   it is broader than the one column.

## 5. Answer to question 3 - other oracle-attributed-to-baseline defects?

- **`evobot_p0_paired.sh` is unrunnable as committed.** Lines 90-91 have a stray
  over-indentation (`        s.place_pose = ps; stages.append(s)` inside a `for` whose body
  is at 4 spaces) - an `IndentationError` in the embedded heredoc. The script that claims to
  produce the genuine A'/B paired execution has **never successfully run**. No `paired.tsv`
  exists anywhere in the repo. So the "P0 paired execution" has no artifact at all - the
  archived table is plan-comparison only, as the Lead concluded.
- **No other** oracle-attributed-to-baseline instance found in this round's documents.

## 6. Verdict

| Lead claim | My verdict |
| --- | --- |
| Archived "A'" is the oracle builder's output | **CONFIRMED** (72/72 byte-identical) |
| Real A' produces a different T06 plan | **CONFIRMED** |
| No other real-A' artifact exists | **CONFIRMED** (21 files, all refusals, 3/17 overlap) |
| 12/5 table is oracle-vs-B | **CONFIRMED** |
| 72/72 is a different, correctly-labelled path | **PATH CONFIRMED, but see section 4** |
| "A'/B paired execution exists" | **REFUTED** - script is unrunnable, no artifact |

**The severity is higher than the mislabel README states.** It is not one mislabelled
column: it is **three different planners all called A'**, one of which (the generic
`rule_planner.py`) declines 100% of the benchmark, plus an unrunnable paired-execution
script. A reader cannot tell from any document which "A'" a given number refers to.

## 7. Reproducers

```
# all 72 byte-identical
python3 setup/acceptance/evobot_t08_gate_audit_20261112/reproducers/repro_provenance.py
```

Artifacts written by that script: `provenance/rebuild_sha256.tsv` (72 rows),
`provenance/planner_matrix.tsv`, `provenance/a_prime_artifacts.tsv`.
