# Regression: does evaluate.py v0.5.0 change any archived T01–T06 verdict?

**Date** 2026-11-12 · **Run by** Team Lead · **Question:** adding a fail-closed evidence layer to the
evaluator is exactly the kind of change that can silently alter old results. Did it?

**Answer: no. 72 of 72 archived verdicts are reproduced exactly.**

---

## 1. Method

For every archived Baseline A-v2 instance that has both an `observation.json` and a `verdict.json`:

```
python3 benchmark/evaluators/evaluate.py benchmark/tasks/train/<task>.json \
        ci-public-window/evidence/baseline_a_v2_gated_20261111/<task>/observation.json
```

and compare the `passed` field against the archived `verdict.json`. The archived files are **read
only**; every re-grade is written to a scratch directory. No simulator, no model call.

## 2. Result

```
graded=72   agree=72   disagree=0
```

| Template | instances | agree |
| --- | --- | --- |
| T01 | 12 | 12 |
| T02 | 12 | 12 |
| T03 | 12 | 12 |
| T04 | 12 | 12 |
| T05 | 12 | 12 |
| T06 | 12 | 12 |
| **total** | **72** | **72** |

The single failure, `T05-train-seed1001`, is reproduced as `False` — so the one negative result in
A-v2 is stable under the new evaluator too, not an artefact of the version that graded it.

**This is a positive result for the v0.5.0 change:** the evidence layer is additive. It does not
re-grade old work, which is what the project's own version discipline requires.

## 3. An incidental provenance fact this run exposed

The archived `verdict.json` files do **not** all carry the same `evaluator_version`:

| `evaluator_version` in the archived verdict | instances |
| --- | --- |
| `0.2.0` | **27** |
| `0.3.0` | **40** |
| `0.4.0` | **5** |
| total | 72 |

So **"A-v2 = 71/72 graded by one evaluator" is not literally true.** The 72 archived verdicts were
produced across three evaluator versions. That does not change the pass count — and §2 shows all 72
are reproduced by the current evaluator, which is the stronger guarantee — but it does mean the batch
cannot be described as a single-version measurement.

**What may be said now:** A-v2's 71/72 is reproduced exactly by `evaluate.py` v0.5.0, so the result is
version-robust. **What may not be said:** that the 72 verdicts were all produced by one evaluator
version, or that any of them was produced by v0.5.0.

## 4. Why this matters beyond bookkeeping

The project's integrity rules forbid re-grading history into a better-looking result. The converse
risk is equally real and less often checked: a *stricter* evaluator silently failing old passes, which
would look like a capability regression and send someone hunting a bug that does not exist. This run
rules that out for v0.5.0 on T01–T06.

It does **not** cover T08 — there are no archived T08 passes to regress, because T08 has never
produced `passed=true`.

## 5. Reproduce

```bash
# see the script body in this directory's run_regression.sh
bash setup/acceptance/evobot_lead_regression_v050_20261112/run_regression.sh
```

No thresholds were changed; `evaluate.py` was not modified.
