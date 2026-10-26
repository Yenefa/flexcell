# Teleport carry loop observations — 2026-10-25

Refs #13 and #32. Source base: `86bb4bded897fc90233896acfa629fb5a6623552`
(including #47–#49). This implements the user's requested first step: observe
missing end-effector lookups before changing the carry mechanism.

The earlier A5/B5 window is **already complete**, archived in
[`grasp_b001_20261025`](../setup/acceptance/grasp_b001_20261025/README.md).
It did not reproduce the failure. Do not rerun its old task book as if it were
pending. The next window needs this observation source loaded first.

## Scope

Only `_loop` changes. `_ee` still uses the original 0.5-second lookup and returns
None on an exception. Pose construction, request payloads, the 100/1000-ms
request timeouts, reply interpretation, consecutive failure handling, period
waits and stop conditions are retained. The topic-based teleport engage and
the service-based velocity-servo engage are not changed in this step.

Only teleport emits the new `teleport_loop_summary` event. Existing velocity
pin records and all #49 session/stop identities remain. Each worker owns its
own counters and labels them with its captured object and session; it cannot
borrow a replacement session's counters.

## Record format

One cumulative summary at most once per elapsed second, plus one `final=true`
summary when the loop exits, including an exceptional exit. The final record
can immediately follow a periodic one. All counters start at zero per worker.

| field | meaning |
| --- | --- |
| `schema_version` | 1 |
| `object`, `session`, `backend` | captured worker identity; backend is teleport |
| `started_mono_ns`, `sample_mono_ns` | monotonic nanoseconds, comparable only within the same process lifetime |
| `period_s` | configured period; observation does not alter it |
| `ee_lookup_count` | completed `_ee()` calls in this loop |
| `ee_missing_count` | completed calls returning None; not a count of proven timeouts |
| `ee_missing_streak`, `ee_missing_streak_max` | current and longest run of missing lookup results |
| `ee_lookup_ns_total`, `ee_lookup_ns_max` | measured call duration, including blocking/scheduling; neither is a TF-age measurement |
| `pin_requests` | Gazebo pin requests attempted by this worker |
| `pin_confirmed`, `pin_failed` | requests interpreted as successful, or rejected/raising; not physical-following evidence |
| `pin_skipped_no_offset` | usable EE result but absent offset; separate from TF misses |
| `final` | worker observation closed, **not** confirmation of physical release |

The usual JsonlLog `wall_ts` is also present. Counts are cumulative, not
per-second counts: subtract consecutive records from the same session to get
an interval. A missing final/summary means incomplete evidence, never a healthy
servo. A blocked lookup or process kill may prevent a final record.

The missing fraction is `ee_missing_count / ee_lookup_count` when the denominator
is nonzero. It measures calls, not the fraction of wall time without following.
A high fraction during a failed PICK supports the TF-availability hypothesis;
it does not settle cause without matched motion, timing and pose evidence.
No exception type or transform age is recovered from `_ee`'s None return.

## Evidence boundaries

The frozen #47 files contain 537 PICK rows, 449 carry starts and 19
`set_pose_fail` events. In that specific snapshot, filtering to A/B, excluding
injections and selecting code 23 gives 87 low-rise failures, each with one
same-object start inside its recorded PICK time window. Five older low-rise
records name `target_box` and are a separate population. Counts from another
snapshot must retain their own denominator and input hashes.

This timestamp/object match establishes a logged session start, not continued
physical attachment. The archive has no historical TF-missing denominator to
recompute. Sparse failure logs alone cannot prove requests were never sent.
The carry snapshot retains the known 71-NUL prefix on line 523; it is not edited.

## Verification and overhead

```bash
python3 -m pytest -q src/flexcell/flexcell_skills/test/test_carry_loop_observation.py
```

25 synthetic tests execute the real loop body with scripted TF and transport,
without ROS, Gazebo or a GPU. Sixteen differential cases compare control calls,
request timeouts, waits, stop signals, propagated exceptions and legacy log
records with the pinned pre-change
[`loop_before.txt`](../setup/acceptance/carry_observation_20261025/loop_before.txt)
(SHA-256 `c16814b9662cf417e9be8dbe1018b126d9ec8ea4eedf2df06fdd4f4c2b36e664`).
The remaining cases check missing-lookup denominators, streaks, pin failures,
rate limiting, final records, logger failure isolation and session reset.

This is controlled-input equivalence, not proof of identical real timing.
Clock reads, counters and bounded synchronous logging have a cost. A virtual
I/O test explicitly shows elapsed time increasing while control calls stay the
same. Record a new runtime fingerprint and host load; do not pool this window
into a historical baseline or claim the instrumentation has zero risk/overhead.
The simulator/TF hypothesis is **not yet tested** by these unit tests.

## Manual Agent handoff: GRASP-B-001-PHASE-3

Use the simulation host that produced #47, with its existing teleport profile.
The user forwards this task manually. No model service or new GPU setup is
needed. Do not interrupt another baseline or active action.

1. Deploy the reviewed observation commit supplied with this task. Verify the
   installed `carry_server.py` matches that source, rebuild/restart through the
   host's existing process, and record source SHA, config/world hashes and a
   fresh fingerprint. Missing code is a blocker, not permission to use the old
   silent loop. Keep backend, controller, tolerances and all timings fixed.
2. Require strict health exit 0, `ok=true`, no hard failures, known IDLE and
   carry disengaged. Record load and time. Backend mismatch is a blocker;
   do not silently switch a velocity profile to teleport.
3. Predeclare a single ten-trial diagnostic window: **A1, then A4, then B5**,
   using `setup/111_grasp_probe.py --object target_box_a --trials 1`, then
   `--trials 4`, then `--object target_box_b --trials 5`. Use distinct new
   output files (`A1.jsonl`, `A4.jsonl`, `B5.jsonl`) and retain stdout/stderr/exit.
   The first A1 counts in the window; it is not an extra success filter.
4. After A1, require a known terminal action/cleanup and an unambiguous matching
   teleport session with valid summary fields and a final record. A typed
   physical PICK failure with complete evidence is a valid observation; it
   does not require replacement. Missing telemetry, harness error or an unknown
   action terminal state stops the whole window. Never add Place/Reset to
   erase an unknown state. Remaining trials are NOT_RUN, not silently refilled.
5. Run A4 and B5 only after the preceding segment completes with its prescribed
   count, confirmed cleanup and complete telemetry. Stop on the first harness
   or evidence-integrity failure. No retries, new windows or sampling expansion.
6. Return all original probe rows, Pick/Place/carry/motion logs, health receipts,
   code/config/load identity and a SHA manifest. Distinguish reused snapshot
   data from new rows. Associate PICK evidence ids with session start/stop and
   cumulative summaries by object and time; multiple candidates stay AMBIGUOUS.
   Repeated motion request ids are not unique trial identities.
7. Tabulate each segment/file + trial: typed result, measured rise, lookup/miss
   counts and durations, pin attempts/confirmed/failed, session and matching
   confidence. Compare successful and failed observations within the new
   fingerprint. A high miss count is supporting evidence, not automatic causal
   confirmation. No reproduced failure means NOT_REPRODUCED_IN_THIS_WINDOW.

No mechanism repair, model inference, physical hardware action, statistical
qualification or n≥50/AC@90 unfreeze is delivered or authorized by this task.
