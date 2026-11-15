# T08 push: progress vs net displacement, read-only offline check (2026-11-15)

Issue #232. This directory records what the new offline checker
`scripts/push_net_displacement.py` was run on, and what it produced.

**Nothing here is a task verdict.** The tool reports diagnostic facts; the frozen
evaluator alone decides whether a task passed, and it did not run for this directory.

## The two quantities the tool keeps apart

| name | definition | what it answers |
| --- | --- | --- |
| `progress_m` | sum of the `displacement_along_direction_m` each action report carries | what the executor claims the bounded pushes achieved |
| `net_m` | signed projection of `last measured_after - first measured_before` on the task direction | what the object actually did over the run |
| `difference_m` | `net_m - progress_m` | whether the per-action reports partition the object's motion |

Two rules keep the sum honest:

1. `progress_m` is only defined when **every** report carries a finite
   `displacement_along_direction_m`. A missing or NaN/Infinity value makes it UNKNOWN,
   never zero.
2. A run of more than one attempt is only summed when all attempts record the
   **same requested direction** (sign of `direction_cos`). A recovery attempt
   re-plans its requested direction from the pose it finds; summing a +0.0228 m
   attempt and a -0.0262 m attempt yields a number that is not a displacement of
   anything, so the tool reports UNKNOWN and says why.

`net_m` needs the endpoint poses. When the reports do not carry them the tool
reports UNKNOWN with the missing endpoint named - it does not fall back to the sum.

## Cases run

| case | run directory (unchanged) | reports | endpoint poses |
| --- | --- | --- | --- |
| A | `setup/acceptance/evobot_lead_t08_calib_20261112/batch_samecond_20261112/t1/trial` | push_00.json, push_01.json | absent |
| B | `setup/acceptance/evobot_lead_t08_centre_height_20261112/evidence` (push.json stored as push_00.json) | push_00.json | present |

Direction `(-1, 0)` comes from `benchmark/tasks/t08_fresh_zone_20261112/T08-push-seed5000.json`.
Case B's direction was cross-checked against its own endpoints (x 0.22 -> 0.1143 m),
not only taken from the task file.

## Results

**Case A - UNKNOWN on both quantities.**

- `progress_m`: UNKNOWN - "attempts were requested along different directions; their
  sum is not a displacement". The two reports carry +0.022806 m (`direction_cos` +0.997441)
  and -0.026181 m (`direction_cos` -0.999881).
- `net_m`: UNKNOWN - the first report has no usable `measured_before` and the
  last has no usable `measured_after`.

So for this archived run the two published quantities cannot be reconciled at all:
the archive does not contain the endpoint poses that a net displacement requires.
That is the fact the tool exists to state; it is not a claim about the run itself.

**Case B - KNOWN.**

- `progress_m` = 0.105670 m, `net_m` = 0.105670 m, difference 0.000000 m.
- `magnitude_m` 0.105761 m, `lateral_m` 0.004379 m, `delta_z_m` -0.000104 m.

One attempt, so progress and net quote the same measurement and the difference is
trivially zero. A non-zero difference needs two or more attempts that carry
endpoint poses; `scripts/tests/test_push_net_displacement.py` covers that case with a
synthetic overlapping-window pair (progress 0.14 m, net 0.10 m, difference -0.04 m)
because no archived multi-attempt run carries the endpoints.

## What this does not say

- No task outcome, no pass/fail, no baseline change, no threshold change.
- Two archived runs were checked, not a sweep of all 49 archived `push_*.json` reports.
- The 121.7 / 147.1 mm contradiction and the gripper-gate question from the
  mission update are untouched here.

## Reproduce

    python3 scripts/push_net_displacement.py \
      --task benchmark/tasks/t08_fresh_zone_20261112/T08-push-seed5000.json \
      --run-dir setup/acceptance/evobot_lead_t08_calib_20261112/batch_samecond_20261112/t1/trial \
      --out /tmp/case_a
    python3 -m pytest scripts/tests/test_push_net_displacement.py -q
