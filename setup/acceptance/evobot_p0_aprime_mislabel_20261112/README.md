# P0 defect: the "A′" column of the paired comparison is the ORACLE, not the rule planner

**Date** 2026-11-12 · **Found by** Team Lead while independently re-deriving the P0 paired table
**Severity** high — it does not invalidate any execution result, but it mislabels what was compared
**Status** CONFIRMED by reproduction · fix NOT applied (the affected tool is shared; see §6)

---

## 1. What the round claims

`setup/acceptance/evobot_p0_paired_20261112/README.md` states, and `benchmark/tools/compare_plans.py`
implements, a comparison between:

```
A′  ci-public-window/evidence/baseline_a_v2_gated_20261111/<task>/plan.json
B   setup/acceptance/evobot_baseline_b_v2_20261111/plans/<task>/plan.json
```

with the headline result **17 plans: 12 identical / 5 different**, and the paired execution
result **A′ 9/9, B 9/9, False Success 0**.

## 2. What actually produced `baseline_a_v2_gated_20261111/<task>/plan.json`

Traced through the call chain, all read from the repository:

| Step | File | What it does |
| --- | --- | --- |
| 1 | `ci-public-window/scripts/evobot_batch_v2_gated.sh:110` | calls `evobot_run_b.sh` per instance |
| 2 | `ci-public-window/scripts/evobot_run_b.sh:31` | `python3 experiments/baselines/build_composite_plan.py "$SPEC" "$OUT/plan.json"` |
| 3 | `experiments/baselines/build_composite_plan.py:44` | `stages = sd.spread(ba.plan_from_spec(spec))` |
| 4 | `experiments/baselines/baseline_a_composite.py:18-42` | `plan_from_spec` reads **`spec["expected_goal"]`** for placement and order |

**`plan_from_spec` reads `expected_goal`.** That is the defining property of the *oracle*
Baseline A, the one the project already labelled "Oracle Execution Reference, not a fair baseline"
(`CAPABILITY_REPORT_20261112.md` §4, `PROJECT_STATUS.md`). It is **not** Baseline A′.

## 3. Reproduction (three independent checks)

### 3.1 The archived "A′" plans are byte-identical to the oracle builder's output

```
$ python3 experiments/baselines/build_composite_plan.py benchmark/tasks/train/T04-train-seed1000.json /tmp/x.json
$ diff /tmp/x.json ci-public-window/evidence/baseline_a_v2_gated_20261111/T04-train-seed1000/plan.json
  -> byte identical
$ (same for T06-train-seed1000)
  -> byte identical
```

### 3.2 The real A′ rule planner produces a *different* plan on the disputed templates

```
T06-train-seed1000
  true A′ (runtime/planner/rule_planner_t01_t06.py)  -> 2 moves: zone_2 then zone_1
  archived "A′" plan                                 -> 1 stage: target_box_b -> zone_1 only
  B's plan                                           -> 2 stages: zone_2 then zone_1
```

**The archived "A′" plan agrees with the oracle and disagrees with the real A′.** The document
reports this disagreement as "A′ skips the relay waypoint; B follows the instruction literally" —
but a rule planner that parses "先放左箱，再移到右箱" does produce both hops, which is what the
real A′ does. The behaviour attributed to A′ is the oracle's, because the oracle only needs the
final position.

### 3.3 The oracle's advantage is structural, not a planning difference

`plan_from_spec` derives stages from `expected_goal.order` and `expected_goal.placement`. It cannot
disagree with the answer by construction. So **any** "identical" verdict between it and B is not
evidence about planning intelligence; it is evidence that B reproduced the answer.

## 4. What this does and does not invalidate

| Claim | Effect |
| --- | --- |
| B executed 9 instances in real Gazebo, 9/9 independently passed, False Success 0 | **UNAFFECTED** — B's execution and its independent grading are untouched |
| A-v2 executed 72 instances, 71/72 | **UNAFFECTED** — but this is Baseline **A (oracle)**, exactly as previously labelled |
| "A′ scores 72/72 at plan level on T01–T06" | **PATH CONFIRMED, SCOPE CORRECTED — see §9.** The 72/72 is real and reproducible from `benchmark/rule_saturation_t01_t06.py` → `rule_planner_t01_t06.py`, but it is **plan-layer only and A′ has never been executed in Gazebo**, and there are **three different artifacts called "A′"** in this repo |
| "A′ and B produced 12 identical / 5 different plans" | **INVALID AS LABELLED** — it is *oracle-A* vs B |
| "The 5 plan differences do not change any verdict" | **WEAKER THAN STATED** — it shows the oracle and B agree on outcomes, which is close to tautological |
| "This is the P0 A′/B paired comparison required by the goal §6.4" | **NOT MET** — goal §6.4 requires *same public observation* for both arms; the oracle reads `expected_goal`, A′ does not |

**The consequence that matters:** the P0 gate is not actually closed. What exists is a valid
**oracle-vs-B** comparison (useful: it shows B is not worse than open-book execution on these
instances) plus a separate **plan-level** A′ result (72/72). What does **not** exist is an
**A′-vs-B paired execution** under identical public observation — i.e. the experiment that answers
"does the LLM beat a simple rule parser on the same task, actually executed in Gazebo".

## 5. Why the mislabel was easy to make, and why it is still wrong

`compare_plans.py`'s own docstring says it reads "the ACTUAL archived plans of Baseline A-prime and
Baseline B", and names the directory `baseline_a_v2_gated_20261111`. The directory name says "a_v2",
which readers reasonably read as "the current A". But "A v2" here means *the second measurement of
A*, not *A′*. The two names are one apostrophe apart and the artifact tree gives no other signal.

This is exactly the failure mode the goal §2.4 forbids: **"把规则规划器结果冒充 Agent 智能优势"** has a
mirror image — here the *oracle's* result is presented under the rule planner's name. It is not a
success inflation (nobody claimed a capability), but it is a provenance error that would let a later
reader conclude the A′/B gate is closed when it is not.

## 6. Why the fix is not applied in this document

`benchmark/tools/compare_plans.py` and the `evobot_p0_paired_20261112` README are shared artifacts
that the independent validation lane is currently auditing. Editing them mid-audit would change the
thing under test. The fix is small and is specified here so it can be applied deliberately:

1. Rename the A-side source in `compare_plans.py` to `A_ORACLE_DIR` and label the column
   `A-oracle`; keep the 12/5 table but retitle it.
2. Add a **separate** A′ source: generate A′ plans with `runtime/planner/run_baseline_a_prime.py`
   into a new directory and compare *those* to B.
3. To close the P0 gate properly, **execute** A′'s plans through the same RunComposite path B used
   (`benchmark/tools/run_composite_plan.py`) on the same 9 instances, and grade with the same
   `evaluate.py` v0.5.0. Only that produces an A′/B paired execution.
4. Leave every historical number in place, labelled with what it actually is.

## 7. Minimal next experiment (highest information value in P0)

```
arm A′: run_baseline_a_prime.py -> plan.json -> run_composite_plan.py -> evaluate.py v0.5.0
arm B : already done (9/9, False Success 0)
same 9 instances, same world generator, same evaluator, same tolerance
```

Cost: ~9 Gazebo runs, zero model calls for A′. Output: the first genuine A′/B paired execution in
the project. If A′ also scores 9/9, the honest conclusion is the one already suspected —
**on T01–T06 the LLM has no measurable advantage over a rule parser**, and the agent's contribution
must be sought on templates where rules fail (T08 and beyond). If A′ scores lower, that is the first
evidence of a real planning advantage, and it would need its own verification.

---

## 8. Provenance of this finding

Every claim above was produced by re-running a command in this repository this round; no simulator
was started and no model was called. The two byte-identical `diff` results and the true-A′ plan
contents are the evidence. Reproduce with the commands in §3.

---

## 9. Correction, after independent review (added 2026-11-12)

The independent validation lane (`setup/acceptance/evobot_t08_gate_audit_20261112/PROVENANCE_APRIME_VERIFICATION.md`)
re-derived this document's claims and **confirmed them, while correcting §4**. The Lead verified the
correction directly and accepts it. Recording it here rather than quietly editing §4, because a
finding about provenance errors must not itself hide a revision.

### 9.1 What was wrong in §4

§4 said the 72/72 A′ result was "unaffected". The *path* attribution was right; the **scope** was not.
There are **three distinct artifacts in this repository all called "A′"**, with different behaviour:

| Artifact | Planner module | Behaviour on T01–T06 |
| --- | --- | --- |
| `benchmark/rule_saturation_t01_t06.py:23` | `runtime/planner/rule_planner_t01_t06.py` | parses all six templates; this is the source of **72/72** |
| `runtime/planner/run_baseline_a_prime.py:29` | `runtime/planner/rule_planner.py` (generic) | **declines every T01–T06 instruction** ("no rule matched") |
| `ci-public-window/scripts/evobot_p0_paired.sh:67` | `rule_planner_t01_t06` | parses correctly, but the script cannot run — see §9.2 |
| (plus `experiments/baselines/baseline_a_prime_rules.py`) | third rule set, `BIN_WORD` mapping | cited by `BASELINE_CORRECTION.md:36` |

Verified by hashing the three modules — they are three different files. A reader cannot tell from any
document which "A′" a given number refers to. **That is the real defect, and it is broader than the one
mislabelled column this document originally reported.**

### 9.2 A second, independent defect: the paired-execution script has never run

`ci-public-window/scripts/evobot_p0_paired.sh` — the script whose name claims to produce the genuine
A′/B paired execution — contains a Python heredoc that **does not compile**:

```
lines 90-91 (inside the for-loop body at 4-space indent):
        s.place_pose = ps; stages.append(s)     <- 8 spaces, unexpected indent
python3 compile of heredoc block 1 -> SyntaxError: unexpected indent, line 30
bash -n passes (bash cannot see inside a heredoc); 3 heredoc blocks found, block 1 fails
```

No `paired.tsv` exists anywhere in the repository. So **the "P0 paired execution" has no artifact at
all** — the archived table is plan-comparison only. This independently supports §4's conclusion that
the P0 gate is open, and it means the gate cannot be closed by re-running that script as committed.

### 9.3 Net effect on this document's conclusion

**Strengthened, not weakened.** The original conclusion was "the A′/B gate is not closed". The
correction makes the reason worse: it is not merely that the A-side was the oracle, but that (a) the
A′ label is ambiguous across three implementations, and (b) the script that would have closed the gate
has a syntax error and has never produced an artifact.

**What still stands unchanged:** B's 9/9 real Gazebo execution with False Success 0; the oracle-A vs B
12/5 plan table (correctly relabelled); the need for a genuine A′/B paired execution (task-6).
