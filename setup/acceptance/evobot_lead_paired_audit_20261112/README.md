# The recovery experiment already contains a single-shot arm — and it says one trial changed

**Date** 2026-11-12 · **Zero Gazebo runs — re-analysis of two committed result tables**
**Two findings: the effect is smaller than the audit's already-corrected estimate, and the 2/5 baseline does not reproduce.**

---

## 1. The claim under audit, and what round 19 established

Headline: **closed-loop recovery improves T08 from 2/5 to 4/5.**

Round 19 showed the *sample-size* calculation was circular (sized from the same n=5 effect it was meant to
replace) and that the measured per-draw rate implies a much smaller effect, needing n=53 per arm. **This round
goes further: the 2/5 → 4/5 comparison is not merely underpowered, it is the wrong comparison.**

## 2. The recovery run already contains both arms, paired

`recovery.tsv` records how many attempts each trial took:

```
trial  attempts  achieved_mm  terminal_passed
  1       2         73.95        False
  2       1         90.60        True
  3       1        145.58        True
  4       1         97.45        True
  5       2        122.67        True
```

**A trial with `attempts == 1` is a single-shot trial** — the first attempt *was* the only attempt. A trial
with `attempts > 1` failed its first attempt **by construction**, because recovery only fires on failure. So
this one run yields both arms, **paired, on the same instance, in the same session.**

| view | passes |
| --- | --- |
| first attempt only (the single-shot arm) | **3/5** |
| final, after ≤3 attempts | **4/5** |
| **discordant pairs** | **1 improved, 0 regressed** |

```
McNemar exact on 1 discordant pair: p = 1.0
```

**Within its own experiment, recovery changed exactly one trial out of five.**

## 3. Why the published comparison is the weaker one

The published 2/5 comes from a **different experiment** (`evobot_t08_saturation_diagnosis_20261112`) run at a
different time, not from this run's first attempts. Comparing across them is:

| | published comparison | paired comparison |
| --- | --- | --- |
| arms | two separate batches | same trials, same session, same instance |
| difference | 2/5 vs 4/5 = 2 trials | **3/5 vs 4/5 = 1 trial** |
| variance from batch/conditions | **not controlled** | **removed by pairing** |
| test | Fisher on independent groups | McNemar on discordant pairs |

**Pairing is the stronger design and it halves the runs** — 53 recovery trials would give 53 paired
observations rather than needing 53 + 53 independent ones. Round 19's n=53/arm estimate is therefore
**pessimistic in cost**: a paired design needs far fewer total Gazebo runs, though more than 5.

## 4. The 2/5 baseline does not reproduce from the archive

`repeats.tsv` is the source of that baseline. Grading its recorded columns against the frozen push clauses:

```
trial  disp(mm)   cos      -> verdict on the two recorded clauses
  1    32.63    +0.9849   PASS
  2   137.84    +0.9998   PASS
  3    57.71    +0.9999   PASS
  4     5.05    +0.8290   FAIL
  5     2.63    -0.6633   FAIL

passes: 3/5        the audit states: 2/5
```

**The archived columns give 3/5, not 2/5.**

**I am not calling the audit wrong.** The frozen clause has four sub-clauses; `repeats.tsv` carries only
displacement and cosine. The other two — `|Δz| ≤ 0.020 m` and final pose inside the zone radius — are absent,
and either could fail trial 1 or trial 3. **But that is the finding: the baseline in the headline comparison
cannot be verified from the artifact that is supposed to support it.** The per-trial verdicts are not in this
archive.

## 5. What this leaves

| claim | status |
| --- | --- |
| recovery improves T08 from 2/5 to 4/5 | **NOT SUPPORTED.** Unpaired, and the baseline does not reproduce from its archive |
| recovery improved 1 of 5 trials within the experiment | **SUPPORTED, and it is all the data can say** (McNemar p = 1.0) |
| recovery lifts the distribution's floor from 2.6 mm to 74.0 mm | **SUPPORTED** by the prior audit; independent of pass rates |
| a single draw lands across 20.4 mm, ~15% passing | **SUPPORTED** (round 17, n=197) |
| what n is needed | **round 19's 53/arm is pessimistic — a paired design is cheaper**, but still far more than 5 |

**Net: the recovery mechanism is real and visible in the distribution, and the pass-rate improvement is one
trial in five.** That is what should be written down, instead of 2/5 → 4/5.

## 6. What I did not do

- **Did not run anything.** The decisive step is re-analysis, and it was free.
- **Did not declare the baseline wrong.** 3/5 vs 2/5 is UNRESOLVED without the missing clauses; I record the
  discrepancy rather than resolving it in whichever direction suits the story.
- **Did not touch the evaluator, the clauses, or the thresholds** to reconcile the two numbers.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_paired_audit_20261112/analyse_paired.py
```
