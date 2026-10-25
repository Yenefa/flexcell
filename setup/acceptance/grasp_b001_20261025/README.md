# GRASP-B-001-PHASE-1 — bounded A/B grasp diagnosis, 2026-10-25

**Verdict: `NOT_REPRODUCED_IN_THIS_WINDOW`** — and the window is too small to
claim the fault is gone. See [Statistical power](#statistical-power) before
reading the success counts as good news.

Ten real typed PICK commands against a cold-started Gazebo/MoveIt stack on the
WSL execution host, fixed source `36486780f5bf46add81124aa334400c71be4ae72`.
No model, no GPU service, no robot.

| group | object | trials | succeeded | rise min | rise median | rise max |
| --- | --- | --- | --- | --- | --- | --- |
| A | `target_box_a` | 5 | 5 | +0.0385 | +0.0886 | +0.0965 |
| B | `target_box_b` | 5 | 5 | +0.0706 | +0.0868 | +0.0961 |

Both exits 0, no `harness_error`, strict health clean before and after.

## What this run actually added

The task book expected the native records to be missing attach-gap and carry
stage logs. They are not missing: `pick.jsonl` on this host still holds every
historical PICK with `attach_gap_m`, exact (unrounded) `box_rise_m`,
`carry_offset`, `profile` and `wall_ts`. All twelve failed attempts named in
[`grasp-failures-20261025.json`](../../../competition/iyaic-2026/evidence/grasp-failures-20261025.json)
match on `evidence_id` — 12 of 12, byte-for-byte stage records, no inference.

That converts the question from "we cannot see the failure" to "we can compare
the failure against a fresh success on the same rig", which this archive does.

### The two populations do not overlap

Across 537 PICK records spanning 2026-09-26 → 2026-10-25, `box_rise_m` is
**bimodal**, not a continuum:

| day | PICKs | succeeded | `rise` on success | `rise` on `ERR_GRASP_FAILED` |
| --- | --- | --- | --- | --- |
| 09-26 | 168 | 70 | 0.0305 … 0.1008 (med 0.0797) | −0.0103 … 0.0298 (med −0.0000) |
| 09-27 | 52 | 26 | 0.0306 … 0.0967 (med 0.0785) | −0.0079 … 0.0237 (med +0.0060) |
| 10-04 | 41 | 37 | 0.0352 … 0.1069 (med 0.0715) | −0.0059 … 0.0296 (med +0.0068) |
| 10-05 | 264 | 214 | 0.0312 … 0.1032 (med 0.0733) | −0.0086 … 0.0297 (med −0.0018) |
| **10-25** | **10** | **10** | **0.0385 … 0.0965 (med 0.0877)** | **none** |

The lowest success ever recorded is +0.0305. The highest failure ever recorded
is +0.0298. Failures cluster at **rise ≈ 0 or negative** — the box does not
move, or settles — while successes lift 3–10 cm.

This matters for interpretation: the failure is **not** a weak version of a
success ("servo did not quite keep up"). It is a different outcome. A box that
ends up *lower* than it started was not carried at all.

### What was ruled out

Every measurable intermediate is the same on both sides:

| quantity | historical failures (12) | this window (10) |
| --- | --- | --- |
| `attach_gap_m` | 0.1561 … 0.1671 | 0.1571 … 0.1669 |
| `carry_offset` x | −0.0063 … +0.0061 | −0.0071 … +0.0044 |
| `carry_offset` y | −0.0050 … +0.0070 | −0.0036 … +0.0041 |
| `carry_offset` z | −0.1671 … −0.1560 | −0.1668 … −0.1571 |
| carry backend | `teleport` | `teleport` |
| world `sha256` | `c81c3c09…` | `c81c3c09…` |
| profile | `demo_slow` | `demo_slow` |
| `elapsed_ms` | 7414 … 10919 (med 8265) | 6983 … 8440 (med 7285) |
| `motion_error_code` | 0 | 0 |

So, for this rig:

- **Approach/attach geometry is not the cause.** Attach gaps occupy the same
  10 mm band in both groups, all far inside `attach_radius_m = 0.20`.
- **Offset computation is not the cause.** The full 3-vector, including the
  −0.16 m z, is indistinguishable.
- **Backend selection is not the cause.** Both are `teleport`; the earlier
  `velocity_servo` build is not involved.
- **Code drift is not the explanation.** `pick_server.py` between `1be7ce7`
  (the E-021 source commit) and `main` changed only release/cleanup
  confirmation — `_release_everything` now returns errors, and the
  `ERR_MOTION_FAILED` path releases before returning so a retry is admissible.
  The grasp geometry, `box_follow_min_m = 0.030`, the 2.0 s post-lift settle
  and the rise sampling point are **untouched**. The success rate today is not
  the result of a fix.

What remains unseparated is a transient between attach and carry effect —
physical state, prior-trial residue, or Gazebo service jitter — which the
recorded fields do not capture.

### `set_pose_fail` is a transient, not a sufficient cause

`carry.jsonl` holds 19 `set_pose_fail` events, all `target_box_a`, all
`consecutive = 1`. **One of them lands inside today's successful window**
(15:33:25), and that trial still lifted 0.0911 m. In `carry_server._loop`,
`consecutive_fail >= 3` only stops the servo on `velocity_servo`; on `teleport`
the loop retries indefinitely. A single failed `set_pose` therefore neither
stops the carry nor predicts the outcome.

## Statistical power

This is the part that must not be skipped.

On 2026-10-05 the same rig logged 246 successful and 53 `ERR_GRASP_FAILED`
PICKs — a 17.7 % failure rate. With 10 clean trials, the 95 % Clopper-Pearson
upper bound on the failure rate is **25.9 %**. The historical 17.7 % sits
comfortably inside it.

Put directly: if the failure rate were still 17.7 %, ten consecutive successes
would occur with probability **≈ 14 %**. That is ordinary, not surprising.

**Ten trials cannot distinguish "the fault is gone" from "we did not roll it".**
No claim of repair is made here, and none should be read into this archive.

## The gap this archive cannot close

`carry.jsonl` has no per-PICK identity. `start` events name an object, `stop`
events carry nothing but `backend` and `wall_ts` (1 432 of them), and 276 rows
omit `backend` entirely; 11 early `start` rows predate the object field. The
42 PICK rows carry `request_id = "target_box_a"` / `"target_box_b"` — the object
name, not a goal UUID.

So the task book's requirement to link Pick `request_id` to hover/grasp/lift
motion events **cannot be satisfied from these logs**. Per the book, this is
recorded as `UNKNOWN`, not papered over with adjacency. Making it answerable
needs one field: a goal UUID written into every carry event.

One byte-level defect is kept rather than repaired: line 523 of
`stage_carry.jsonl` begins with 71 NUL bytes (a pre-allocated write on this
filesystem) followed by a complete record. The verifier asserts both the count
and the offset, so the damage cannot silently grow.

## Per-trial record

`attach_gap` and `rise` are taken from the stage log; `rise` is re-derived from
the recorded `before`/`after` poses and must agree to 1e-9.

| grp | trial | goal uuid | evidence_id | attach gap | rise | elapsed |
| --- | --- | --- | --- | --- | --- | --- |
| A | 1 | `4eaeba3d` | `target_box_a-030b030d` | 0.1604 | +0.0911 | 42.6 s |
| A | 2 | `246d4513` | `target_box_a-0c9a0ff6` | 0.1613 | +0.0965 | 43.1 s |
| A | 3 | `453df50a` | `target_box_a-de690c21` | 0.1650 | +0.0886 | 41.8 s |
| A | 4 | `473dd719` | `target_box_a-d7fcc68a` | 0.1571 | +0.0385 | 42.6 s |
| A | 5 | `ad252426` | `target_box_a-31654279` | 0.1620 | +0.0466 | 41.8 s |
| B | 1 | `3b74b502` | `target_box_b-386e6fbe` | 0.1606 | +0.0961 | 43.5 s |
| B | 2 | `e182e43c` | `target_box_b-4b3900d5` | 0.1616 | +0.0822 | 43.3 s |
| B | 3 | `25fd12e3` | `target_box_b-9c123cb8` | 0.1656 | +0.0706 | 43.0 s |
| B | 4 | `5bde9c6c` | `target_box_b-c68e678e` | 0.1667 | +0.0868 | 43.5 s |
| B | 5 | `519ff2ea` | `target_box_b-0c9a0a9c` | 0.1669 | +0.0918 | 42.5 s |

Every row: `precondition.ok = true`, reset saw `task_state = IDLE`, goal
accepted, termination confirmed, cleanup `ok`, `pick_ok = true`, `error_code = 0`.

`health_before.json` and `health_after.json` are **byte-identical**
(`4728f7f0…`) — ten reset/pick/place/cleanup cycles left the stack in the same
state it started.

## Files

| file | what it is |
| --- | --- |
| `A.jsonl`, `B.jsonl` | probe rows, one JSON object per trial |
| `A.stdout`, `B.stdout` | probe summary lines (Wilson interval, rise min/median/max) |
| `A.stderr`, `B.stderr` | empty; both are committed as empty files |
| `A.exit`, `B.exit` | real exit codes, `0` and `0` |
| `health_before.json`, `health_after.json` | strict `flexcell_admin.py health` receipts |
| `controllers_before.json` | `117_ros_ready.py controllers` — all three active |
| `env.txt` | the resolved environment the window ran under |
| `head.txt` | source commit and branch at run time |
| `identity_sha256.txt` | digests of `decision_policy.py`, `pick_server.py`, `111_grasp_probe.py`, `flexcell_world.sdf` |
| `git_status.txt` | the 131 pre-existing untracked acceptance-log entries, so the dirty tree is stated not implied |
| `stage_pick.jsonl` | **snapshot** of `~/.ros/flexcell/pick.jsonl` (537 rows, 2026-09-26 → 2026-10-25) |
| `stage_carry.jsonl` | **snapshot** of `carry.jsonl` (1 900 rows, one NUL-prefixed) |
| `stage_place.jsonl` | **snapshot** of `place.jsonl` (308 rows) |

The three `stage_*` files are copies of live append-only logs, taken while the
stack was running. Their digests are of the snapshot, **not** of the source
files' final state; the source files were neither truncated nor reformatted.

## Reproducing this archive's claims

```
$ python3 setup/acceptance/grasp_b001_20261025/verify_grasp_b001.py
60 checks, 0 failed
RESULT: CONFIRMED (window reproduced, historical failures not)      exit 0

$ python3 setup/acceptance/grasp_b001_20261025/selftest_verify_grasp_b001.py
13/13 cases behave as declared                                     exit 0
```

Stdlib only, no ROS, no network. The self-test copies the archive to a scratch
directory and requires rejection of: a lowered rise, a deleted trial, an
injected `harness_error`, a non-zero exit, a dirty health receipt, a wrong
commit, a missing historical evidence id, historical failures shifted into the
success band, a forged `request_id` in the carry log, an extra trial, a
`rise_m` that its own poses do not support, and an attach gap outside the
radius. Both run in CI.

## Scope

This is **not** a smoke qualification, not a benchmark window, and not a
FSM/Hybrid comparison. It reproduces neither the dual-object A→B context of
E-021 nor its policy decisions. `n ≥ 50`, AC@90 and formal qualification remain
frozen and are not touched by this archive.

The host stack was cold-started for this run and **left running** afterwards;
it is owned by this session, not by a pre-existing deployment.
