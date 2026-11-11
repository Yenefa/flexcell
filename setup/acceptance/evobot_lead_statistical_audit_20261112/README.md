# Lead statistical audit — is "4/5 vs 2/5" evidence of a skill improvement?

**Date** 2026-11-12 · **Auditor** Team Lead · **Input** `evobot_push_recover_20261112/evidence_v2/recovery.tsv`,
`evobot_t08_saturation_diagnosis_20261112/evidence/repeats.tsv`

**Purpose.** Before any downstream document quotes "closed-loop recovery improves T08 from 2/5 to 4/5",
check whether that difference is distinguishable from noise. It is not.

---

## 1. The comparison, exactly as recorded

| Arm | Config | Terminal clause passes |
| --- | --- | --- |
| S | single-shot `PushObject`, `contact_height_m=0.0200`, one attempt | **2/5** |
| R | closed-loop recovery, same contact height, ≤3 attempts | **4/5** |

Fisher exact, two-sided, on the terminal clause only:

| Comparison | p |
| --- | --- |
| R 4/5 vs S 2/5 | **0.5238** |
| R 4/5 vs S 3/5 (the RTF=0 control arm) | **1.0000** |
| R 4/5 vs S 0/5 (contact height 0.030) | 0.0476 |

**Conclusion: the headline 2/5 → 4/5 improvement is not statistically distinguishable from chance.**
The only comparison that clears alpha=0.05 is against the *0.030 contact-height* arm — i.e. against a
configuration that could not establish contact at all. That comparison does not isolate the recovery
strategy; it conflates the strategy with the contact-height fix that both R and S share.

Wilson 95% intervals overlap almost completely:

```
recovery      4/5 = 80%   Wilson95 [0.376, 0.964]
single-shot   2/5 = 40%   Wilson95 [0.118, 0.769]
```

**Sample size needed** to detect 80% vs 40% at alpha=0.05, power=0.80, two-sided, equal arms:
**n ≈ 22 per arm.** The round has n=5. It is short by a factor of ~4.4.

## 2. What the numbers DO support

Directionally consistent and mechanistically sensible, but not established:

| Quantity | single-shot | recovery |
| --- | --- | --- |
| min displacement (mm) | 2.6 | 74.0 |
| median (mm) | 32.6 | 97.5 |
| max (mm) | 137.8 | 145.6 |
| spread (mm) | 135.2 | 71.6 |

The recovery arm's floor moved from 2.6 mm to 74.0 mm. **The lower tail is what the strategy actually
fixes** — it retries when a push produced almost nothing. That is a real mechanism, visible in the data,
and it is a *distributional* claim, not a pass-rate claim. It is testable with a proper n.

## 3. A risk the round did not record: the recovery arm is crowding the ceiling

The frozen clause requires `min_displacement_m ≤ d ≤ max_displacement_m` = **[0.030, 0.150]**.

Recovery trial 3 reached **145.58 mm — 4.4 mm below the ceiling.** Median is 97.5 mm.
An iterative strategy that keeps requesting the shortfall *will overshoot the ceiling* on a run where
the first push is already strong, and the failure mode is then a **FAIL for pushing too far**, which is
the opposite of the failure the strategy was built to fix.

This is not hypothetical: the earlier fixed-step control arm already produced a 156.77 mm overshoot
(recorded in `FIXEDSTEP_CONTROL_RESULT.md`), i.e. **the ceiling is reachable in practice.**

**Therefore the recovery policy needs an explicit ceiling guard before it is run at larger n**, or a
larger-n batch will manufacture a new class of failure that looks like the strategy regressing.

## 4. Consequences for what may be written

| Statement | Allowed? |
| --- | --- |
| "Recovery raises the terminal pass count from 2/5 to 4/5 on this instance" | ✅ as a raw observation, with n=5 and p=0.52 stated |
| "Recovery improves the T08 success rate" | ❌ not supported |
| "Recovery is a usable T08 skill" | ❌ `passed` is still false (no bundle); unseen not run |
| "Recovery fixes the near-zero-displacement tail" | ✅ supported by min 2.6 → 74.0 mm; state as distributional |
| "T08 is solved / Level 4 reached" | ❌ |

The existing `RESULT_V2.md` is already careful on most of these. It says the 2/5→4/5 difference
"尚未做统计检验" (no statistical test performed). **This document performs that test. The answer is
p=0.52.** Any later summary that quotes 4/5 vs 2/5 as an improvement must carry this number.

## 5. Reproduce

```
python3 setup/acceptance/evobot_lead_statistical_audit_20261112/statistics.py
```

No simulator, no model calls, no thresholds changed.
