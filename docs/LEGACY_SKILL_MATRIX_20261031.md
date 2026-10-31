# The legacy skill matrix: what #59 asked for, and what it shows

Status: measured. Two windows, `skill_backend=legacy` on both carry backends, the same
five declared tasks and the same 60 mm verifier tolerance as every other window on this
manifest. Nothing was relaxed, and the failure codes did not move. The measurement itself
holds a surprise that matters more than the pass/fail verdict.

## What #59 asks

> Prove that switching backends did not quietly relax anything.
>
> - existing offline tests and gate tests all green;
> - `skill_backend=legacy` × `carry_backend={teleport, detachable_joint}` combinations
>   covered;
> - any tolerance change must be zero; if one is unavoidable, list it and justify it
>   (treated as not passed);
> - failure-code semantics unchanged.
> - runs in CI; zero runs on the real machine.

## Result

Five windows, one manifest (`infra/legacy-parity-window.json`, declaration
`6e815d4f…` for all five), no replacement trials:

| window | skill | carry | worst verified error | verdict |
| --- | --- | --- | --- | --- |
| `parity-teleport` | MTC | teleport | 0.171 mm | pass |
| `parity-velocity_servo` | MTC | velocity servo | 0.230 mm | pass |
| `parity-detachable_joint` | MTC | joint | 12.252 mm | pass |
| `legacy-skill-teleport` | **legacy** | teleport | **12.206 mm** | pass |
| `legacy-skill-detachable_joint` | **legacy** | joint | **45.007 mm** | pass |

Per case (worst verified error; pick/place attempts):

| case | MTC × teleport | MTC × joint | legacy × teleport | legacy × joint |
| --- | --- | --- | --- | --- |
| normal / A | 0.17 mm (2/1) | 2.20 mm (1/1) | 3.86 mm (2/1) | 19.81 mm (1/1) |
| normal / B | 0.09 mm (1/1) | 2.25 mm (1/1) | 12.18 mm (1/1) | 21.89 mm (1/1) |
| dual_object | 0.10 mm (3/2) | 12.25 mm (2/2) | 8.20 mm (2/2) | 45.01 mm (2/2) |
| recovery_once | 0.09 mm (2/1) | 2.16 mm (2/1) | 12.21 mm (2/1) | 18.38 mm (2/1) |
| budget_exhaustion | expected failure | expected failure | expected failure | expected failure |

**Tolerances:** one value, 60 mm, in all five windows — the report refuses to compare
windows verified against different tolerances, and it passed that check. **No change of any
kind.** Failure codes: `ERR_NONE` for the four passing cases and
`ERR_RECOVERY_EXHAUSTED` for the declared negative, identical in every window.

## The finding, which is not the verdict

All five pass, so nothing was quietly relaxed. But look at the spread:

- the **carry** backend moves the worst error from 0.17 mm to 12.25 mm (MTC);
- the **skill** backend moves it from 0.17 mm to 12.21 mm (teleport) and puts the
  joint combination at **45.007 mm against a 60 mm tolerance**.

So the dominant term is not the carry backend — it is `skill_backend=legacy`. This
qualifies, and partly corrects, what [#80](https://github.com/Yenefa/flexcell/pull/80) and
[#81](https://github.com/Yenefa/flexcell/pull/81) say: "the joint backend is ~10x less
accurate" is true **within `skill_backend=mtc`**. Across skill backends the difference is
much larger, and the joint-under-legacy combination is within 15 mm of the declared
tolerance — i.e. it passes today with less margin than anything else measured in this
project.

That is precisely the situation #59 exists to catch: not a moved threshold, but a
combination whose margin is thin enough that a bad landing would flip it.

## Repeat window: the 45 mm is repeatable, not a fluke

The first joint × legacy window used 75 % of the tolerance on one landing, so it was
repeated with the same manifest and the same declaration:

| case | run 1 (mm) | run 2 (mm) |
| --- | --- | --- |
| normal / A | 19.808 | 34.829 |
| normal / B | 21.894 | 22.816 |
| dual_object | 27.596 / 45.007 | 24.851 / 33.915 |
| recovery_once | 18.376 | 27.625 |
| budget_exhaustion | expected failure | expected failure |

Across the two windows, ten placements: **18.4–45.0 mm, mean 27.7 mm**, worst landing at
**75 % of the declared tolerance**. Both windows pass, and both are a long way from the
0.17–0.23 mm the same tasks reach on MTC × teleport.

So the combination is not a lucky pass — it is a *repeatably thin* pass. Any tolerance
below roughly 46 mm would have failed it, and the spread (18 → 45 mm) is wide enough that
a third window could plausibly land outside. That is worth knowing before this combination
is quoted as "passing": it passes **this** criterion, at a margin nothing else in the
project comes close to using.

## Why this is not a regression

Nothing in this branch changes the legacy skill path: `place_server` / `move_to_pose` are
untouched, and the carry-side changes (pre-position reference, false-attach injection) are
either default-off or only on the joint path. These are the **first** measurements of
`skill_backend=legacy` on these five tasks against the 60 mm criterion; earlier baselines
in the repository were velocity-servo/MTC. So this is a first measurement, not a change of
behaviour — but it also means the legacy path was never held to this measurement before.

## Boundaries and what it does not establish

- Two windows for joint × legacy (the thinnest cell), one for the others: still a verdict
  matrix, not a rate.
- The `45.007 mm` is one landing away from the 60 mm line. Nothing here says whether it
  would pass on a second window; a repeat would be cheap and should happen before anyone
  quotes the joint × legacy combination as "passing".
- Run location: CI per #59. GitHub Actions is still refusing to start jobs on this account
  (annotations point at failed payments or a spending limit), so these two windows were run
  on the local stack and reported as such. The CI job
  (`legacy-skill-matrix-smoke`) is added and will execute the same two windows and the same
  comparison once runners come back.
- D3 stays **NO_GO**; default backend unchanged; n ≥ 50 frozen.
