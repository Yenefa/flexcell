# Issue #232 — read-only offline check: push PROGRESS vs final NET DISPLACEMENT

**Lane** gate-auditor · **Date** 2026-11-12 · **Offline, read-only, no simulator, no model calls.**

```
check_progress_vs_net.py        the tool
test_check_progress_vs_net.py   19 tests, every one an edge case that actually bit us
results/                        scan of evobot_t08_instance_pose_20261112
results_calib/                  scan of evobot_lead_t08_calib_20261112
```

## The three quantities, defined and kept apart

| field | definition |
| --- | --- |
| `reported_progress_m` | sum over the run's push action records of the per-action reported displacement projected onto the task direction. **What the skill said.** A claim, not a measurement. |
| `net_displacement_m` | `(post − pre) · u` — the signed along-direction net movement of the box. Positive = along, negative = against. **What the world did.** |
| `difference_m` | `net_displacement_m − reported_progress_m` |
| `net_magnitude_m` | `|post − pre|`, including lateral drift. Reported **beside** the along number, never instead of it. |
| `lateral_m` | movement across the task direction |
| `arm_travel_m` | sum of `ee_travel_m`: **end-effector** travel, not box travel, never substituted for it |
| `travel_to_net_ratio` | `arm_travel_m / |net_displacement_m|` |

`u` is the normalised XY task direction, taken from the artifact's own `expected_goal.push.<obj>.direction`, or from an explicit `--direction "dx,dy"`. **Nothing is assumed**: no direction means `UNKNOWN`, never a default of −x.

## UNKNOWN is not zero

A missing endpoint, a non-finite value, an empty direction, or an action with no usable reported value makes that quantity `UNKNOWN` and the trial status `UNKNOWN`. Nothing defaults to `0.0` — a missing measurement is not a stationary box.

## Motion buckets are descriptive, not pass/fail

`FORWARD` / `REVERSE` / `LATERAL` / `STATIONARY` / `UNKNOWN`, from the measured net vector (`STATIONARY_M = 1 mm` reporting floor, lateral wins when it exceeds the along component). **The tool emits no pass/fail, reads no expected_goal thresholds, and writes nothing outside `--out`.**

---

## What the scan found

### 1. The 4.6x case — reported one action, measured the whole run

`runs/U_shot/seed3002/t1` in `evobot_t08_instance_pose_20261112`:

| quantity | value |
| --- | --- |
| reported_progress_m | **0.030446** |
| net_displacement_m (along) | **0.140287** |
| difference_m | **+0.109841** |
| ratio | **4.61x** |
| arm_travel_m | 0.132 |
| net_magnitude_m | 0.140988 |

This is the case the Lead described as "reported 0.0306 m corresponded to 0.1403 m of real travel" and as a "4.6x error". **All three of those numbers are confirmed exactly** — 0.0306, 0.1403, 4.6x.

**But the cause is a scope mismatch, not a measurement failure.** `push_00.json` reports the displacement observed inside *one action's* measurement window — it says so in its own detail field: *"contact lost at increment 4: object moved 0.0306m of 0.0900m requested while the arm kept advancing"*. The box then continued to move. Comparing one action's report against the run's total net is comparing two different scopes, and yields a ratio that means nothing.

**This is why the tool reports `n_actions` next to `reported_progress_m`.** A difference is only interpretable when the scope matches. `U_shot/seed3002` has `n_actions = 1`; `U/seed3002` has `n_actions = 3` and its numbers behave completely differently.

### 2. The retreat-transit signature — arm travel is not box travel

`runs/U/seed3002/t1`:

| quantity | value |
| --- | --- |
| reported_progress_m | 0.101353 |
| net_displacement_m | **0.046007** |
| difference_m | **−0.055346** (over-reported) |
| arm_travel_m | **0.358411** |
| travel_to_net_ratio | **7.79** |

The arm travelled 0.358 m to move the box 0.046 m net, because the recovery layer backs off and re-approaches between attempts. **Reading `arm_travel_m` as box displacement would produce a 7.8x "error" that does not exist.** This is the same trap as the 4.6x case, mirrored: one confuses scope, the other confuses which body moved.

### 3. Sign — a reversal reports NEGATIVE, never a flipped magnitude

`overlay_candidate_20261112/runs/cand_2.json`:

```
reported_progress_m  -0.01079   (direction_cos = -0.9942)
net_displacement_m   -0.054328  (motion = REVERSE)
difference_m         -0.043538
```

Both negative — sign agrees here — but the reported magnitude is **5.0x too small**. The failure mode that motivated this tool was the opposite: reported **+0.017** while the box went **−0.065**. The tool makes that structural: `net_displacement_m` takes its sign from the projection onto `u` and is never derived from the reported number, so a wrong sign in the report cannot propagate into the measured value. Covered by `test_sign_flip_differs_by_the_whole_gap` (−0.082, not −0.048).

### 4. Coverage: 15 of 27 collected trials are UNKNOWN, and that is the finding

| family | trials | status |
| --- | --- | --- |
| `evobot_t08_instance_pose_20261112` | 6 | 6 MEASURED |
| `overlay_candidate_20261112` | 8 | 8 MEASURED |
| `batch_samecond_20261112`, `trial_20261112_t*` | 5 | **UNKNOWN — no endpoints recorded** |
| `staged_candidate_20261112` | 10 | **UNKNOWN — no endpoints recorded** |

15 of 27 trials carry a push claim but no ground-truth endpoints, so no net displacement can be computed for them and the tool says so instead of skipping them. **A skipped trial is invisible; an UNKNOWN row is a coverage gap you can count.**

---

## Acceptance criteria

| # | criterion | status |
| --- | --- | --- |
| 1 | signed net displacement along the task direction, arbitrary planar directions | `unit_direction` normalises any XY vector; tested on (0,1) and (3,−4) |
| 2 | forward, reverse, lateral, stationary, missing endpoint, non-finite | all six exercised on **real archive data**; non-finite additionally unit-tested |
| 3 | inputs untouched, output to a NEW directory | `--out` only; `results/` and `results_calib/` are new |
| 4 | diagnostic facts only, no pass/fail | `test_output_has_no_pass_fail_field` asserts no `passed`/`verdict` key is emitted |

## Reproduce

```bash
python3 test_check_progress_vs_net.py
python3 check_progress_vs_net.py --root <abs>/setup/acceptance/evobot_t08_instance_pose_20261112 --out results
python3 check_progress_vs_net.py --root <abs>/setup/acceptance/evobot_lead_t08_calib_20261112 --direction=-1,0 --out results_calib
```

`--direction=-1,0` is required for the calibration archive because those records do not store the commanded direction. It is supplied by the operator, not assumed by the tool.

## Not done, deliberately

- No task pass/fail conclusion, per issue #232.
- No change to `contracts/push.py`, the evaluator, thresholds or any acceptance evidence.
- `reported_progress_m` is not corrected or reconciled — the tool reports the gap, it does not decide which side is right.
