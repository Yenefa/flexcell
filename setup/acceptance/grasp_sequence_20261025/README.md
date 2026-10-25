# GRASP-B-001-PHASE-2 — is the failure transient or contextual?

**Verdict: `SEQUENCE_HYPOTHESIS_REJECTED`.** The ordered A→B window that
[#32](https://github.com/Yenefa/flexcell/issues/32) was heading towards would
have tested a hypothesis the existing archive already rejects, so it was not
run. This note records the test, the numbers, and the two of my own
intermediate claims that the test killed.

Read-only analysis of the 537 PICK records archived in
[`../grasp_b001_20261025/`](../grasp_b001_20261025). No new robot time, no new
Gazebo run, no code change to any skill server.

```bash
python3 setup/acceptance/grasp_sequence_20261025/analyse.py
python3 setup/acceptance/grasp_sequence_20261025/selftest_analyse.py
```

`analyse.py` asserts every number it prints and exits non-zero if the archive
stops supporting it. `selftest_analyse.py` corrupts private copies of the
archive in six ways and requires five rejections plus one positive control.

## First: the population was wrong

58 of the 537 records are deliberate scenario injections
(`recovery_demo_v1`, `exhaust_demo_v1`). They carry `error_code 23` and, read
naively, look exactly like physical grasp failures. Counting them as evidence:

| | naive | injections removed |
| --- | --- | --- |
| records | 537 | 479 |
| grasp failures (`23`) | 150 | **92** |
| baseline failure rate | 27.9 % | **20.4 %** of 451 measured PICKs |

They also cluster by construction, which manufactured a sequential correlation.
With them in, the odds ratio for "failure follows failure" came out at **3.73**.
With them out it is **1.74** on a two-proportion z. The first number was an
artefact of the injections, and it was the number I was about to design an
experiment around.

## The sequence test

Sessions are reconstructed from `wall_ts` with a 120 s gap, then adjacent pairs
inside a session are classified.

| previous PICK | PICKs | next PICK fails | rate |
| --- | --- | --- | --- |
| success | 326 | 61 | 0.187 |
| grasp failure (`23`) | 76 | 21 | **0.276** |

Two-proportion z = **1.74** — below the 1.96 needed to claim a carry-over at
95 %. A failure is followed by a success (55) more often than by another failure
(21), and success→failure (58) is as common as failure→success (55). The
failure behaves as a **memoryless 19–28 % coin flip per attempt**, which is what
"transient" means operationally.

Baseline does not drift with position in the session either (0.10–0.40 across
indices 0–8 of the long sessions, n=10 each) — no warm-up, no thermal creep.

### Infrastructure errors are a different animal

| previous | n | next fails | rate |
| --- | --- | --- | --- |
| `30` MoveToPose contention | 11 | 11 | **1.000** |
| `41` gz transport | 5 | 5 | **1.000** |
| `21` observe/parse | 5 | 4 | 0.800 |
| `22` pose stream stalled | 1 | 1 | 1.000 |

These *are* contextual and highly sticky: once the action server is left with a
live goal ("another MoveToPose goal is active") or the gz transport wedges,
every subsequent PICK in the session fails. They are 28 of 537 records and they
are not grasp failures. Any future window has to report them separately or the
denominator is meaningless.

## Falsified on the way

**`set_pose_fail` does not mark the failures.** Counting those events inside
each PICK's own `[wall_ts - elapsed_ms, wall_ts]` window:

| | PICKs | windows containing a pin failure |
| --- | --- | --- |
| success | 358 | **17 (4.7 %)** |
| grasp failure | 88 | **2 (2.3 %)** |

Pin-service failure is *more* common on successes. The teleport backend does not
abort on repeated pin failure (`carry_server.py:353` only self-stops for
`velocity_servo`), which made this a plausible silent mechanism — the data says
no.

**`status` is not evidence.** `status` separated the two populations perfectly
(1 vs 2, zero overlap, n=332) and looked like the strongest signal in the
archive. It is `derive_status('PICK', outcome)` (`pick_server.py:255`) — derived
from the outcome it appears to predict. Withdrawn.

**The stale-spawn-pose idea.** Failure rows sometimes carry `box_before` equal
to the world-file spawn pose `[0.22, 0.0, 0.0175]` to the last bit, which reads
like a frozen observation rather than a measurement. Only **3 of 92** failure
rows do; 89 carry a measured pose. Withdrawn.

## What the failure actually looks like

All 92 measured failures start with the box at rest (`box_before.z` in
0.0102 … 0.0178). They end in three shapes:

| outcome at the post-settle sample | count |
| --- | --- |
| **below** where it started | 52 |
| did not move | 5 |
| rose < 3 cm | 35 |

The dominant shape is a box that ends *lower* than it began: the lift completes,
the 2.0 s settle elapses, and the box is at or under its rest height. That is
not a servo that was slightly too slow — `pick_server.py:441` already sleeps
2.0 s precisely because the pin servo needs ~2 s to reach its plateau.

## What is still unknown, and what would close it

The one measurable that could separate these shapes is the carry servo's own
per-tick behaviour inside the failing PICK. It is not recoverable:

```
stop events 1432, of which 0 name a session, 0 name an object
start events 449  ->  983 stops are re-engages or no-ops
```

`carry_server.py:252` writes `{'event': 'stop', 'backend': ...}` *after*
`_object_id` has been cleared on line 248, and never writes the `session` that
`_on_stop` already added to `_retired_sessions` on line 247. Three separate
callers (`_engage` replace, `_on_release`, `_check_worker`) are
indistinguishable in the log. The identity is in memory and is dropped at the
write.

So the next change is instrumentation, not an experiment: record
`session`/`object`/`cause` on `stop`, and `session` on `set_pose_fail`. Then a
single PICK can be traced through engage → pin ticks → release, and the three
shapes above become attributable. That touches a frozen file and per #32's sixth
acceptance item needs its own recording design and fingerprint acceptance
before any window is run with it.
