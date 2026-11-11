# Paired run in progress — early observation changes what the binding constraint is

**Date** 2026-11-12 (round 27). Run started round 26 on domains 200-205.

## Trials so far

| trial | attempts | achieved_mm | terminal_passed | failed_clauses |
| --- | --- | --- | --- | --- |
| 1 | 1 | 149.40 | **False** | push:target_box_a |
| round-26 isolation trial (separate) | 2 | 92.60 | **False** | push:target_box_a |

## Why this matters already

Both trials have displacement **inside** the frozen [30, 150] mm bound — 92.60 and 149.40 mm — so the
**displacement sub-clause passed in both**, and both failed on `push:target_box_a`.

**The binding constraint is not displacement.** That invalidates the framing of rounds 17–19, which treated the
height sweep's displacement bands as the pass criterion.

**Consequence:** round 19's 14.7% per-draw rate, and the n=53/arm derived from it, are wrong in the same way —
they score passes by displacement band rather than by the full conjunctive clause. **They should not be cited.**

**The pre-registered analysis is unaffected**: it uses the evaluator's actual `terminal_passed`, not a proxy.
The registered prediction (first-attempt ~15%, final ~38%) is likely too optimistic and will be reported as
refuted if so.

## Status

Run continues. No result claimed. Analysis goes to `RESULT.md` against the unchanged pre-registration.
