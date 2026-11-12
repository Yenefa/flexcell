# THE RETREAT LIFT WORKS: drag-back goes from +0.0596 to 0.0000

Seed 3002 - the seed that failed in every configuration tried for six rounds - now lands inside
the zone.

## Paired run, isolate overlay, one parameter

`T08-push-seed3002`, biased staging (y = box_y + 0.07), `distance 0.040`, `contact_height 0.020`.
Both runs use the **same modified overlay build**; only `retreat_lift_m` differs.

| `retreat_lift_m` | box start | furthest -x | box end | push | **drag-back** | net | zone distance |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **0.0** (frozen behaviour) | 0.1900 | 0.1594 | 0.2189 | -0.0306 | **+0.0596** | +0.0289 | 0.1290 **OUT** |
| **0.08** | 0.1900 | 0.0788 | 0.0788 | **-0.1112** | **+0.0000** | **-0.1112** | **0.0139 IN** |

**The drag-back is gone: exactly 0.0000.** The box ends at its furthest point instead of being
carried back, and finishes 0.0139 m from the zone centre against a 0.06 radius.

## What changed, and what did not

Changed, in an **isolated overlay workspace** (`/tmp/t08_push_ws`) only:

- `contracts/push.py`: a new `retreat_lift_m` default of 0.0, and the retreat's z term becomes
  `face[2] + p['retreat_lift_m']` instead of `face[2]`.
- `push_server.py`: `retreat_lift_m` added to the parameters the node reads.

Not changed: the repository copy of `contracts/push.py`. **The frozen file is untouched** - the
overlay is what `AUTHORITY_SCOPE.md` section 1 authorises, and the default of 0.0 means the
build behaves identically to the frozen version unless the parameter is set.

No threshold, evaluator, TaskSpec or acceptance evidence was modified.

## Why this is the predicted result and not a lucky run

Rounds 64-66 established the drag as ~0.06 m, independent of the approach, and round 67 traced
it to `push.py:512-513` carrying `face[2]` through unchanged. **The prediction was that raising
the frame before it loses x would let the trailing fingers clear the box.** The measured drag
went to zero, which is what that mechanism predicts.

## Honest limits

- **One paired run, one seed.** This is a strong single result, not a rate. The same discipline
  that made round 62's prediction get narrowed by round 63 applies here.
- **0.08 was chosen, not derived.** It exceeds the box height (0.035) plus the finger offset,
  but a smaller lift might suffice and a larger one might cost time.
- **The 0.1112 push is larger than the baseline's 0.0306** - the lift also seems to change how
  the push itself proceeds, which is not explained.
- **Not evaluated.** This run has not been through the frozen evaluator with a complete
  evidence bundle. T08 remains `CALIBRATION_UNSUPPORTED`.

## The next test

Same paired design across seeds 2000, 3001, 3002 and at least one held-out seed, baseline vs
lift, then the frozen evaluator on any run that satisfies the task.