# GRASP-B-001-PHASE-3 — corrigendum to the #52 window

Written 2026-10-27, against archive `grasp_phase3_window_20261026` at main
`e7a6963` (the merge of #52). No raw file in the archive changes. v1
(`verify_phase3_window.py`, `selftest_verify_phase3_window.py`) is kept byte for
byte as the historical record; the correction lives in the v2 pair beside it and
in the section below that replaces "The boundary that keeps this honest".

## What stands

Every factual assertion in the window survives, and was re-run:

- Ten declared trials, `A1` → `A4` → `B5`, ten distinct carry sessions, ten
  finals, ten sessions joined by exact `carry_offset` equality.
- 639 end-effector lookups, 0 missing. 639 pin requests, 638 confirmed, 1
  rejected — in a trial that passed. The failing trial itself: 0 misses, 0 pin
  rejections, normal session close.
- The box trails its pinned pose in every trial: +0.7 mm to −71.7 mm. The single
  failure (B5-2, code 23, rise +0.0234 m) is the largest lag in the sample.
- Strict health clean before and after; source tree unmodified at start; world
  sha unchanged from #47.

The two mechanism hypotheses are dead **for this window**: a miss in the failing
trial is directly falsified by that trial's own counters, and a rejected pin in
it by the same counters.

## What is withdrawn

### 1. "+17.4 mm is the lowest rise this mechanism can produce"

It is not a bound. It is `0.089058 − 0.071698 = 0.017360 m`, the arithmetic of
this window's shortest arm travel and this window's largest observed lag. Ten
trials, one trajectory, one source, one world.

Three problems, in increasing order of severity:

1. **A sample maximum is not a physical maximum.** Nothing in the archive
   constrains lag from above. The number is the largest of ten observations.
2. **The window contradicts its own mechanism.** The README reads the lag as
   "a body in free fall for one pin period: 0.5 · 9.81 · 0.1² = 49 mm". The
   observed worst lag is 71.7 mm, 1.46 periods. If 49 mm were the cap, the floor
   would be `0.089058 − 0.049050 = +0.040008 m`. Two "bounds" 22.6 mm apart, from
   the same archive, is the signature of a number that is not a bound.
3. **It cannot be applied to the historical population at all.** The historical
   records in `grasp_b001_20261025/stage_pick.jsonl` carry `box_before`,
   `box_after`, `error_code`, `evidence_id`, `profile` and timestamps. They
   carry no arm travel. The floor needs this window's travel. There is no
   historical analogue to compute, so the floor cannot partition that
   population — not because the partition is wrong, but because it is
   uncomputable from the evidence cited.

### 2. "So the 54 historical negative-rise failures are a different population"

Withdrawn, and the archive argues against it:

| quantity | value |
| --- | --- |
| historical code-23 failures (natural) | 92 |
| their rise support | −0.0103 m … +0.0298 m |
| median | −0.00027 m |
| below zero / exactly zero / above zero | 54 / 3 / 35 |
| at or above this window's +0.0234 m | **7** |

This window's failure sits inside the historical support, and seven historical
failures rose at least as far. A single observation above the population median
is not evidence of a different generating mechanism; with 35 of 92 historical
failures positive, a positive rise is an ordinary member of that population, not
an alien one. The honest statement is the weaker one:

> This failure does not match the historical *central tendency*, and it was not
> reproduced in ten trials. Whether it shares the historical mechanism is not
> decided by this archive.

### 3. "The two leading hypotheses are now dead" (scoped)

True of this window's conditions, not of the mechanisms in general:

- 0 misses in 639 lookups bounds the window miss rate below 0.47 % (95 %, rule
  of three). A rate bound excludes "the misses are frequent here"; it does not
  exclude "a miss occurs under a condition this window never sampled".
- The per-trial exclusion is the strong one: the failing trial recorded zero
  misses and zero pin rejections, so neither caused *that* trial to fail.
- Nothing in the window tests a rejected pin and a failure in the same trial,
  a different backend, a warm stack, or a second object geometry.

## What replaces it

`verify_phase3_window_v2.py` keeps every factual check and replaces the two
over-claims with what the archive supports:

- the envelope is asserted as arithmetic, labelled sample-scoped, and paired
  with a check that the historical archive contains no arm travel (so the
  envelope cannot migrate);
- the two candidate floors are computed and asserted to disagree, which is the
  evidence that neither is a physical bound;
- containment replaces separation: the window's failure is asserted to lie
  inside the historical support, with 7 of 92 at or above it;
- the miss figure is reported as a 95 % upper bound on a rate;
- the power of a clean ten-trial window is computed (10.2 % at the historical
  20.4 % rate) and asserted in range, so "not reproduced" cannot harden into
  "does not happen";
- rise and lag are asserted to move together as a **rank association**
  (ρ = +0.976, n = 10), which is all the archive shows. Causation is not
  asserted, and the verdict block says so.

Dropped: "the lag is continuous, not two populations". It passed at a 20 mm cut
(5 over, 5 under) and would fail at 10 mm or 30 mm. It was never a fact, only a
threshold. It is printed as a description now.

`selftest_verify_phase3_window_v2.py` runs the positive control and nine
mutations, all ten as declared. Two of them exist because of this corrigendum:

- trimming the historical population to negatives only — v1 still passes, v2
  fails, so the withdrawn conclusion is now enforced against the evidence;
- lifting the window's failure above the historical support — v2 fails, forcing
  a human to re-narrate rather than inherit this text.

## Replacement for "The boundary that keeps this honest"

> ## The envelope, and what it is not
>
> If the box merely trails a gripper it stays in contact with, it cannot end
> below its starting height. In this window the shortest arm travel was
> 89.1 mm and the worst observed lag 71.7 mm, so **within these ten trials the
> lowest rise the arithmetic allows is +17.4 mm**.
>
> That is an envelope over ten trials, not a physical bound. Nothing here
> constrains lag from above: one period of free fall is 49 mm and the observed
> worst is 71.7 mm, so the mechanism offered for the lag already exceeds the
> figure that would cap it. Nor can the envelope travel: the historical archive
> records box endpoints, not arm travel, so the same arithmetic cannot be run
> on the 92 historical failures at all.
>
> What the historical population does say is narrower and more awkward for the
> story above: the window's failure (+0.0234 m) sits inside the historical
> support (−0.0103 … +0.0298 m), and 7 of the 92 rose at least as far. So the
> failure seen here is **not** the historical median, and it is **not**
> separable from the historical population by this archive. #48's bimodal
> reading is not overturned; it is also not confirmed. The historical failure
> was not reproduced in ten trials, and at the 20.4 % historical rate a clean
> ten-trial window happens about 10 % of the time either way.

## Reproduce

```bash
python3 setup/acceptance/grasp_phase3_window_20261026/verify_phase3_window_v2.py
python3 setup/acceptance/grasp_phase3_window_20261026/selftest_verify_phase3_window_v2.py
```

Expected: `verify_phase3_window_v2.py` exits 0 with `CONFIRMED` / `NOT
ESTABLISHED` blocks; the selftest prints `10/10 cases behave as declared`.
v1 still exits 0 unchanged — both are true statements about the same bytes; v2
is the one that does not claim more than they contain.

## Consequence for the next window

The next window's decision rule cannot be "did the historical shape reappear".
On this archive the only live question is the one #52 already pre-declared:
sample the box *between* pins. If it oscillates between the pin target and
target − ~50 mm, `box_follow_min_m` is measuring a sampling instant; if it sits
at a constant offset, the lag is real and the physics question is open. Both
outcomes are decided by the trajectory, not by a rise threshold or a comparison
with 92 old failures.
