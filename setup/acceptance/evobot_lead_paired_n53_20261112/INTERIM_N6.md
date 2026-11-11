# Interim: 6 of 66 trials, zero passes, and the pre-registered overshoot has occurred

**Date** 2026-11-12 07:57 · **NOT the result. n=6 of a registered 66. No claim is made.**

## The six graded trials

| trial | attempts | achieved_mm | terminal_passed | failed_clauses |
| --- | --- | --- | --- | --- |
| 1 | 1 | 149.40 | **False** | push:target_box_a |
| 2 | 2 | 0.00 | **False** | unmoved:target_box_b, push:target_box_a |
| 3 | 2 | 1.64 | **False** | push:target_box_a |
| 4 | 2 | **201.51** | **False** | push:target_box_a |
| 5 | 2 | 24.60 | **False** | push:target_box_a |
| 6 | 2 | 149.29 | **False** | push:target_box_a |

**0 of 6 passed.** Five of six took a second attempt, so every first attempt failed; no trial improved to a pass.

## Three observations worth recording now, because they were pre-committed

**1. The overshoot risk fired.** Trial 4 reached **201.51 mm — 51.5 mm past the frozen 150 mm ceiling.** The
pre-registration predicted *"at least one trial will fail by exceeding 150 mm"* and required it be counted
**against** the strategy. It is.

**2. Displacement is still not the binding clause.** Trials 1 and 6 landed at 149.40 and 149.29 mm — inside
[30, 150] — and still failed on `push:target_box_a`. That confirms the round-27 finding on a second and third
trial: **the conjunctive clause fails on a sub-clause other than displacement**, and every round 17–19 figure
scored by displacement band is invalid.

**3. Recovery has shown no benefit in this run.** It fired in 5 of 6 trials and changed the outcome in **none**:
0 discordant pairs favouring recovery. The pilot's 4/5 is not reproducing.

## What this is not

**It is not the result.** n=6 against a registered 66. The registered analysis is McNemar on paired
discordant pairs, and with 0 discordant pairs favouring recovery the test is undefined, not significant.
**A pass rate of 0/6 is consistent with a true rate as high as ~40%** (rule of three: 95% upper bound ≈ 3/6).
Reporting "recovery fails" on this would be the fifth instance of the proxy-substitution error.

## However — the pre-registered prediction is already falsified in direction

The registration predicted first-attempt ~15% and final ~38%. Observed: **first-attempt 0/6, final 0/6.**
**If this holds to n=66, the prediction is refuted and must be reported as refuted**, exactly as
`PREREGISTRATION.md` §5 commits me to. I am recording the direction now, before more data arrives, so that I
cannot quietly restate it later.

## Status

Run continues (chunk 1 of 6 at trial 6). Analysis goes to `RESULT.md` when either n=66 is reached or the run is
stopped, whichever happens, against the unchanged pre-registration.
