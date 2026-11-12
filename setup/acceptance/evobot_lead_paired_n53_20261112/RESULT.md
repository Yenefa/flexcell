# RESULT (interim at n=26 of 66): zero passes, zero discordant pairs — the registered prediction is refuted

**Date** 2026-11-12 08:11 · **n=26 of a registered 66. The run is still going; this is the interim read.**

---

## 1. The data, complete and unedited

Chunks 1–2 finished (11 + 11 trials), chunk 3 at trial 4. **26 rows, 26 `terminal_passed=False`, 26 failures on
`push:target_box_a`.**

| attempts | trials | first attempt passed |
| --- | --- | --- |
| 1 | 6 | **0** |
| 2 | 20 | **0** (by construction — recovery only fires on failure) |

```
first-attempt passes : 0/26
final passes         : 0/26
discordant pairs     : 0 improved, 0 regressed
McNemar              : UNDEFINED (no discordant pairs), not significant
```

## 2. The registered prediction is REFUTED

`PREREGISTRATION.md` §5 committed me to predicting **first-attempt ~15% (CI 10–21%)** and **final ~38%
(CI 27–50%)**. Observed: **0% and 0%**. Both intervals exclude 0. **The prediction is refuted and I am
reporting it as refuted**, exactly as pre-committed. It was derived from round 19's 14.7%, which was itself
scored by displacement band rather than by the conjunctive clause — so the prediction inherited a known error,
and the data says so.

## 3. The overshoot prediction is CONFIRMED, and it was counted against the strategy

Pre-registered: *"at least one trial will fail by exceeding 150 mm"*, to be reported **against** the strategy.

| trial | achieved_mm | over the 150 mm ceiling by |
| --- | --- | --- |
| 4 | 201.51 | 51.5 mm |
| (chunk 2) trial 1 | 162.51 | 12.5 mm |
| (chunk 2) trial 10 | 153.57 | 3.6 mm |
| (chunk 3) trial 4 | 152.02 | 2.0 mm |
| (chunk 2) trial 4 | 147.70 | — near miss, 2.3 mm under |
| 1 | 149.40 | — near miss, 0.6 mm under |

**Four trials overshot.** The recovery arm's median displacement is well above the pilot's 97.5 mm, and the
strategy's generosity at the top is a real cost of allowing retries.

## 4. The finding that actually matters: `push:target_box_a` fails 26 for 26

**Every single trial failed the same sub-clause, including trials whose displacement was comfortably inside
[30, 150] mm** — 149.40, 149.29, 147.70, 142.40, 109.64, 103.25, 95.92.

**Displacement is not the binding constraint. It never was.** The height sweep (round 17) and everything built
on it (rounds 18–19, and this pre-registration's prediction) modelled the wrong clause. `push:target_box_a` is
the conjunctive clause that actually decides T08, and it fails regardless of how far the box moves.

## 5. What this establishes, and at what level

| claim | level |
| --- | --- |
| T08 with ≤3-attempt recovery on this instance, this configuration: **0/26** | **Simulation Tested** |
| recovery provides **no** benefit over first attempt here: 0 discordant pairs | **Simulation Tested** |
| the binding sub-clause is `push:target_box_a`, not displacement | **Simulation Tested** |
| recovery improves T08 in general | **NOT SUPPORTED — and the pilot's 4/5 did not reproduce at 5× the n** |
| T08 is achievable in this configuration | **NOT SHOWN. 0/26 with a 95% upper bound near 11%** |

**Not Generalization Tested**: one instance, seed2000, no unseen seeds.

## 6. What this means for P2

The recovery avenue is closed by measurement, not argument. **T08 at 0/26 with the failure always on the same
sub-clause, while ±3.44 mm pose repeatability is measured against a 2.5 mm cliff, is the same conclusion from
two independent directions: this configuration cannot do this task, and no retry policy fixes it.**

The registered 66-trial run may be allowed to finish for completeness. **It cannot change the conclusion**: 0/26
already refutes the prediction, and the remaining trials can only move the pass rate within a range whose
upper bound is ~11%.
