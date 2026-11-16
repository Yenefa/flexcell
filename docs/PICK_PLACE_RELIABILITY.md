# Pick/place reliability — first bounded window

Scope: **FUNCTIONAL_SMOKE_ONLY**. Reuses `scripts/sim_smoke.py` and the original
`normal` / `dual_object` cases. No object, target, tolerance or task-budget change.
Not a hardware-grasp claim, not a complete ordinary-task regression, not a
baseline promotion.

## Frozen window

| order | label | case |
| --- | --- | --- |
| 1 | NORMAL_1 | normal |
| 2 | DUAL_1 | dual_object |
| 3 | NORMAL_2 | normal |
| 4 | DUAL_2 | dual_object |

Backend `velocity_servo`, skill backend `legacy`. Independent initialization per
slot, own output directory, sequential. 360 s per slot, 1440 s per window.

## Environment

| item | value |
| --- | --- |
| host | Core i7-13620H / 16 GB, WSL2 Ubuntu 24.04, CPU-only (llvmpipe) |
| ROS | Jazzy, Gazebo Harmonic 8.15, MoveIt 2.12 |
| branch | `feat/physical-pick-place-reliability-20261116` @ `2ca40eb` |
| build | `colcon build --merge-install`, 11 packages |

## Offline tests

```bash
python3 -m unittest discover -s experiments/physical_capabilities/pick_place_reliability/tests -v
```

53 tests: one-result parsing, the single-run rule, the source-change scope,
unknown-terminal detection, window stop behaviour, the completion flag, timeout
and signal cleanup, the driver-verdict gate, non-finite values, corrupt-log
isolation, the window-freeze gate, and the artifact aggregator. No simulator, no
ROS.

## Results (6 windows, 24 slot attempts)

| window | NORMAL_1 | DUAL_1 | NORMAL_2 | DUAL_2 |
| --- | --- | --- | --- | --- |
| main `ebe27f07` | 7.64 mm | ok 28.2 s | 13.95 mm | ok 28.3 s |
| branch #1 | 11.74 mm | ok 29.6 s | 7.70 mm | ok 28.8 s |
| branch #2 | **UNKNOWN** (harness) | NOT_RUN | NOT_RUN | NOT_RUN |
| branch #3 | 8.07 mm | ok 29.6 s | 9.96 mm | ok 29.8 s |
| branch #4 | 13.40 mm | ok 29.6 s | 9.13 mm | ok 29.1 s |
| branch #5 | 7.61 mm | ok 29.1 s | 2.70 mm | ok 29.4 s |

Completed slots: 20. `dual_object` 10/10. Normal placement error, n = 10:
mean **9.19 mm**, stdev 3.30, min **2.70 mm**, max **13.95 mm** (5.2x spread).

## Reproduce the numbers

```bash
python3 experiments/physical_capabilities/pick_place_reliability/analyze_windows.py \
  /artifacts/pick-place-1 /artifacts/pick-place-2 --out analysis.json
```

`analysis.json` recomputes, from artifacts only: per-slot drop/verify error, the
last two `move_to_pose` targets, the error distribution, and whether any two runs
used a different release target.

A slot enters the statistics only when it has exactly one `run-*` directory, a
readable `result.json`, no unknown terminal state, a `PASS` harness status, a
succeeded task outcome and a numeric final error. The window's own `results.json`
is checked first: a slot the driver marked `UNKNOWN` (outer timeout, interrupt,
unknown terminal) is not reclassified as `OK` even when a raw `PASS` result
survived on disk, and unreadable window metadata leaves the slot `UNKNOWN`.
Everything else is counted separately and listed in `excluded` with a reason, so a
failed or unmeasured slot never becomes a zero-error sample. A non-finite
(`NaN`/`Inf`) final error or target is treated as unmeasured, not rounded into the
statistics. Two run directories for one slot are reported as `AMBIGUOUS` instead
of silently reduced to the first one. A truncated JSONL line is recorded against
its slot (`log_errors`) and its measurement stays `null`; the remaining windows
are still analyzed.

The freeze covers what the slot can execute or load, not only Python packages:
`src/flexcell/**`, `infra/**`, `scripts/**`, `worlds/**`, `config/**`,
`setup/flexcell_admin.py`, `plan_execute.py` and the window's own driver,
preregistration and tests. A changed `worlds/*.sdf` therefore changes the
`source_before` / `source_after` comparison instead of passing as an unchanged
scene (386 files, 0.07 s on this host).

A window whose `source_unchanged` is `false` is reported as `NOT_COMPARABLE`
rather than silently pooled with the frozen runs: its slots are listed in
`excluded` with the changed files, `summary.windows_not_frozen` counts such
windows, and the analyzer exits non-zero. A changed scene can still be evidence,
but it is not a frozen regression sample.

## Finding 1 — the command is fixed, the result is not

The last two `move_to_pose` targets are byte-identical in every run:

```
release 0.120000, -0.150000, 0.189500
retreat 0.120000, -0.150000, 0.289500
```

yet the placement error spans 2.70-13.95 mm. Perception and planning are not the
source; the variance is created during execution.

Aggregated check (`unique_release_target_sets`): **1** across all ten completed
slots — every run commanded exactly the same two poses.

## Finding 2 — the error is already present at the first post-release sample

`place` drop error and `verify` final error agree in every slot:

| run | place drop error | verify error |
| --- | --- | --- |
| main NORMAL_1 | 8 mm | 7.6 mm |
| main NORMAL_2 | 14 mm | 14.0 mm |
| branch NORMAL_1 | 12 mm | 11.7 mm |
| branch NORMAL_2 | 8 mm | 7.7 mm |

Aggregated check (`max_place_verify_delta_mm`): **0.6 mm** across the ten
completed slots. Slots that lack either measurement are excluded from this delta
instead of being filled with zero.

What the number does and does not bound: `place_server` samples `drop_err` after
the release, after the gripper opens, and after `settle_time_s`
(`place_server.py:435-450`). The agreement therefore bounds what changed
**between those two samples**; it does not exclude movement in the interval from
release to the first sample. Slip during settle, servo drift and grasp offset
stay open until there is continuous pose evidence across the release instant.

## Finding 3 — one UNKNOWN was a harness race, not a robot failure

Branch window #2 stopped at NORMAL_1 with `ACTION_TERMINAL_UNKNOWN`, while the
same run recorded a successful pick (`rise 0.096 m`), a successful place
(`drop error 0.007 m`) and a completed task. The client had printed:

```
CLIENT_GOAL_SEND_TIMEOUT: acceptance unknown; stop batch and inspect task state
```

The goal reached the server (it executed) but the acceptance reply did not reach
the client inside its 30 s window. With a per-slot `ROS_DOMAIN_ID` every slot pays
a cold DDS discovery, so that window is tight under CPU load.

Harness fix applied (client only, fail-closed semantics unchanged):

- `wait_for_server` 10 s -> 30 s
- goal-acceptance window `min(30, timeout)` -> `min(90, timeout)`

After the fix: 2 windows, 8/8 slots completed, 0 UNKNOWN. This is weak evidence
(1/4 before vs 0/8 after) but the mechanism is understood and the change cannot
turn a failure into a pass.

## Boundaries

- Ordinary carry uses a simulation-only backend; results are a bounded functional
  regression, not a hardware grasp claim and not the full push-task acceptance.
- The 5.2x spread is an observation about one host and one backend, not a
  reliability rate; n >= 50 remains frozen.
- Carry-side offset is not recorded today (`carry.jsonl` stores events only), so
  the execution variance cannot yet be attributed to grasp offset versus servo
  drift. Adding that observable touches the frozen carry backend and needs an
  explicit go.
