# Pre-registration: the paired recovery experiment (n≈66), written before results exist

**Registered** 2026-11-12 07:32 (+08:00), **before any trial outcome was observed.**
**Status: RUNNING in background. This file is the commitment; results go elsewhere when they land.**

---

## 1. The question, in one sentence

> In T08, does allowing up to three push attempts instead of one increase the number of trials that pass the
> frozen terminal clause — **measured pairwise within the same trial, on the same instance, in the same
> session**?

## 2. Why this design, and not the published one

Rounds 19–20 established two problems with the published 2/5 → 4/5, and this design fixes both:

| problem | fix |
| --- | --- |
| the arms came from **different experiments**, so batch variance was uncontrolled | **one run yields both arms**: `attempts == 1` *is* single-shot; `attempts > 1` failed its first attempt by construction |
| n=5 with a **circular power calculation** | n≈66 trials → 66 paired observations, sized from round 19's measured per-draw rate rather than the observed effect |

**Pairing is also cheaper**: 66 trials give 66 paired observations, where independent arms would need 106.

## 3. Design, fixed now

| item | value |
| --- | --- |
| task | `benchmark/tasks/t08_dev/T08-push-seed2000.json` (unchanged) |
| `contact_height_m` | 0.0200 (unchanged) |
| attempt budget | 3 (`push_recover` default, unchanged) |
| trials | 6 chunks × 11 = **66** |
| evaluator | frozen `evaluate.py` v0.5.0, four push sub-clauses (unchanged) |
| chunking | domain rotates per chunk (241…246) to avoid the measured CycloneDDS participant exhaustion; see `run_paired.sh` |
| per-trial observation | `(first_attempt_passed, final_passed)` where `first_attempt_passed = (attempts == 1 and passed)` |

**No threshold, evaluator, task or contract is touched. The evidence script itself is called UNMODIFIED.**

## 4. Primary analysis — fixed before data

**McNemar exact test on discordant pairs**, two-sided, alpha = 0.05.

| outcome | pre-registered interpretation |
| --- | --- |
| p < 0.05 favouring recovery | the pass-rate claim is **supported** at this n |
| p ≥ 0.05 | the pass-rate claim is **NOT supported**; report the point estimate and its CI, claim nothing |
| any trial where `first_attempt_passed` is true and `final_passed` is false | **counts as a regression** and must be reported individually, not netted away |

## 5. My prediction, recorded so it can be wrong

From round 17 (a single draw lands across 20.4 mm, ~15% passing) and the ≤3-attempt budget:

| quantity | predicted |
| --- | --- |
| first-attempt pass rate | **~15%** (95% CI 10–21%) |
| final pass rate | **~38%** (95% CI 27–50%) |
| discordant pairs | **~15 of 66**, favouring recovery |
| McNemar | **borderline at n=66** — this may still be inconclusive, and I am saying so in advance |

**If the measured first-attempt rate comes in near 40% rather than 15%, round 17's pooled estimate does not
transfer to this instance and I will report that as a refutation of my own model, not as a nuisance.**

## 6. A risk I am pre-registering because the prior audit flagged it

The frozen clause has an **upper** bound of 150 mm. The recovery arm's median in the pilot was **97.5 mm** and
its best trial reached **145.58 mm — 4.4 mm below the ceiling.** More attempts means more chances to overshoot.

**Prediction: at least one trial will fail by exceeding 150 mm rather than by falling short.** If that happens,
it is a real cost of the strategy and must be reported against the strategy, not hidden by netting.

## 7. What will NOT be claimed regardless of outcome

- **Not Generalization Tested.** One instance, seed2000. Nothing here transfers to unseen seeds.
- **Not a Threshold Change.** The clause is unchanged; if the strategy overshoots, the answer is that it
  overshoots, never that the ceiling should move.
- **Not P2 completion.** T08 also requires fail-closed trajectory verification that cannot be faked by
  pick-carry-place; a pass-rate result says nothing about that.

## 8. Where results will go

`setup/acceptance/evobot_lead_paired_n53_20261112/RESULT.md`, written only after the run completes, with the
raw per-trial tsv copied in unchanged. Any deviation from this plan will be stated in that file rather than
silently adopted.
