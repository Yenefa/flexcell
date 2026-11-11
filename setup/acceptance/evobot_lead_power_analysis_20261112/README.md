# Don't run n=22: the sample-size calculation was circular, and the real n is 53 per arm

**Date** 2026-11-12 · **Zero Gazebo runs — arithmetic over two existing measurements**
**Verdict: the planned 22-per-arm test would be under-powered (0.44) and its null would mean nothing.**

---

## 1. What I was about to do, and why I stopped

The most important open capability question is whether closed-loop push recovery genuinely improves T08. A
prior audit found the headline **4/5 vs 2/5** is not distinguishable from chance (Fisher p = 0.52) and concluded:

> *"Sample size needed to detect 80% vs 40% at alpha=0.05, power=0.80, two-sided, equal arms: **n ≈ 22 per
> arm.** The round has n=5. It is short by a factor of ~4.4."*

The environment is intact (all five setup files present, no stray sim, task spec present), so I could have
launched 44 trials. **I checked the arithmetic first, and it does not hold.**

## 2. The circularity

`n ≈ 22` was computed to detect **80% vs 40%**. Where do 80% and 40% come from? **4/5 and 2/5** — the same
n=5 sample the study exists to replace. **The effect size used to size the experiment was estimated from the
experiment being sized.** When n=5 estimates are that unstable (Wilson interval for 4/5 is [0.376, 0.964]), the
required n inherits the instability: it is sized to confirm the *observed* effect, including whatever noise
inflated it.

## 3. An independent estimate of the per-draw rate

Round 17 measured what a single contact-height move actually does, over **197 archived samples**: the only
passing displacement band (69.92 mm, inside the frozen [30, 150] mm) takes **14.7%** of draws; every other band
fails the clause. That estimate does not come from the 5-trial recovery experiment at all.

With `push_recover`'s budget of 3 attempts, the implied rate is `1-(1-0.147)^3` = **38.0%**.

| | assumed by the audit | implied by measurement |
| --- | --- | --- |
| single-shot | 40% | **14.7%** |
| recovery (≤3 attempts) | 80% | **38.0%** |
| effect size | 40 points | **23 points** |
| n per arm for 80% power | 19.6 → **22** | **52.4 → 53** |

```
$ python3 compute_power.py
n per arm to detect 80% vs 40%     : 19.6  -> the audit rounded to 22
n per arm to detect the REAL effect : 52.4  -> round UP
REQUIRED: 53 trials per arm = 106 Gazebo runs total.
power at n=22 : 0.44  (target 0.80)
```

**A 22-per-arm run has 44% power.** It would most likely return a non-significant result, and that result
would be **uninterpretable** — indistinguishable from *"no effect"* and *"not enough data"*. Running it would
cost ~44 Gazebo trials and buy a null nobody could act on.

## 4. What this changes, and the decision it hands back

| option | cost | what it buys |
| --- | --- | --- |
| n=22 per arm | ~44 runs | power 0.44 — **not worth running** |
| **n=53 per arm** | **~106 runs** | power 0.80 on the measured effect size — **the honest requirement** |
| n=5 (current) | done | p=0.52, no claim — what exists today |

At roughly 3 minutes per trial **106 runs is 5+ hours of continuous Gazebo**, against a one-instance-at-a-time
lock. That is a resource decision, not an analysis I should quietly absorb into a round — and it is the kind of
spend the mission asks me not to take unsanctioned.

**So the recommendation is: do not run the 22-per-arm test; either fund the 53-per-arm one or accept that the
recovery effect stays unestablished.**

## 5. What this does NOT say

- **Not that recovery does not work.** The audit's distributional finding stands and is independent of power:
  the recovery arm's **floor moved from 2.6 mm to 74.0 mm**. That is a real mechanism — it retries when a push
  produced almost nothing — and round 17 supplies the reason it is needed: a single draw lands anywhere in a
  20 mm distribution.
- **Not that 14.7% is exact.** It is a **pooled** estimate from contact-height moves across several archived
  batches, not from the single instance the recovery script uses. It is independent of the 5-trial sample, which
  is what makes it useful here, not unbiased.
- **Not a threshold argument.** No criterion is touched. The band shares come from the committed sweep and the
  frozen clause.

## 6. The synthesis worth recording

Two rounds of archive measurement now fit together:

| finding | source |
| --- | --- |
| a single contact-height draw lands across a 20.4 mm range, only ~15% of it passing | round 17, n=197 |
| recovery retries a short push and lifts the floor from 2.6 mm to 74.0 mm | prior audit, n=5 |
| the two combine to a predicted 38% vs 15% — **a real but modest effect** | this round |

**That is why 4/5 vs 2/5 looked dramatic and is not:** at n=5 the two arms can differ by 3 trials purely by
chance, and the underlying effect, while real, is around 23 percentage points — not 40.

## 7. Reproduce

```bash
python3 setup/acceptance/evobot_lead_power_analysis_20261112/compute_power.py
```
