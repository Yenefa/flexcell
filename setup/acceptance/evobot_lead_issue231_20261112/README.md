# Issue #231 — log retention and missing-item checking

**Date** 2026-11-12 · **Lane** sim-push · **Scope: logging only.** No motion logic, task
definition, acceptance rule or threshold was touched. Offline: no Gazebo, no ROS, no network.

```
python3 verify.py <run-dir> --profile push      # check one run
python3 verify.py --scan <root> --profile push  # check a whole batch
python3 test_verify.py                          # 23 tests
```

Exit codes: **0** complete · **1** missing/incomplete · **2** checker misused or checked nothing.

---

## 1. What #231 asks for, and what this delivers

| Acceptance criterion | Delivered by |
|---|---|
| Runs use separate output directories; raw failure data preserved | §2 root cause + `MISFILED` detection that proves when they do not |
| Missing items listed explicitly, never a silent success | `MISSING` / `EMPTY` / `MISFILED` / `UNMARKED` findings, exit 1 |
| Verification runs without robot simulation | pure filesystem check; no ROS import, no simulator, no network |

Covers all three required outcomes: **normal completion**, **execution failure**,
**startup failure** (§4).

---

## 2. Root cause of the missing log, measured — and it is still live

The trigger was that the Lead's own push runs produced no `push.jsonl`. That is not a
crash. It is a configuration gap with a specific shape:

* `push_server.py:124-125` declares `log_dir = '~/.ros/flexcell'` and
  `log_file = 'push.jsonl'` as **defaults**.
* `sim_profile.py:117-119` rewrites `log_dir` per run for **every node present in the
  params file**.
* `week1.yaml` has blocks for `observe_server`, `pick_server`, `place_server`,
  `verify_server`, `carry_server`, `task_fsm_server` (and `move_to_pose.yaml` for
  `move_to_pose_server`) — **there is no `push_server` block anywhere.**
* So `push_server` keeps its default and **every run appends to one global
  `~/.ros/flexcell/push.jsonl`.**

Measured on this checkout: that file holds **351 records from 21 distinct
`request_id`s**, spanning several unrelated runs and eras.

And `push.jsonl` is not the only one — the same class of defect affects others, shown
below. The counts were taken by scanning the real acceptance tree, not by inspection:

```
$ python3 verify.py --scan .../evobot_t08_contact_calibration_20261112/runs --profile push
6 of 6 run(s) incomplete
    MISFILED push.jsonl   ... (found at /home/ros/.ros/flexcell/push.jsonl)

$ python3 verify.py --scan .../c13_constrained_20261110 --profile pick_place
5 of 5 run(s) incomplete
```

**This is why the checker distinguishes MISSING from MISFILED.** When the data exists in a
shared file, a human who goes looking finds something and reasonably assumes it belongs to
the run in hand. `os.path.exists(run_dir)` cannot see that; naming the shared path can.

### The fix this implies (not applied — outside a logging-only scope)

Add to `week1.yaml`:

```yaml
push_server:
  ros__parameters:
    log_dir: ~/.ros/flexcell
    log_file: push.jsonl
```

`sim_profile.py` then rewrites `log_dir` per run automatically, the same way it already
does for the six servers that are configured. **Not done here**: it changes runtime
configuration for every future run on a shared branch, and #231 is scoped to logging
*verification*. It needs the Lead's decision and a run to confirm.

---

## 3. Design decisions that are load-bearing

**Required items are declared, never inferred from disk.** A checker that derives its
expectations from the files it is checking always passes. Priority: `--required` ›
`logs/expected_logs.txt` manifest › `--profile` preset.

**A zero-byte log is EMPTY, not present.** A file that recorded nothing is not evidence
that nothing happened. (Measured: 0 zero-byte logs in the current tree — the check still
matters for future runs.)

**A scan that finds no runs exits 2, not 0.** This was a real defect in the first version
of this tool. Pointed at a tree using the older `<run>/skills` layout it found zero runs
and printed `0 of 0 run(s) incomplete` — a clean bill from a check that inspected nothing,
which is precisely the defect class #231 exists to catch. Both layouts are now handled
(257 `sim/skills` + 13 `skills`) and an empty scan is an error.

**A stale shared file is not called MISFILED.** Also a real defect found on real data: a
run from 2026-11-10 was reported `MISFILED task_fsm.jsonl` against a global file last
written **2026-10-05** — five weeks before the run existed. It cannot contain that run's
records, and saying so would send a reader to a file that does hold `task_fsm` data, just
not theirs. The tool now compares the shared file's mtime against the run's own earliest
log: older means `MISSING ... predates this run`; newer means `MISFILED` with an explicit
**"MAY contain ... it cannot be used as this run's log"** hedge, because mtime alone cannot
prove ownership.

---

## 4. The three outcomes

| outcome | how detected | what must be present |
|---|---|---|
| `normal` | a result artefact (`trial_record.json`, `verdict.json`, `evidence_bundle.json`, `result.json`) | the full required log set |
| `failed` | `invalid_infra.txt` / `failure.json` / `error.json` | partial logs are legitimate, **but a missing required log is still a finding** |
| `startup` | `startup_failure.json` / `startup_failure.txt` | zero skill logs is expected; the marker itself must exist |
| `unknown` | none of the above | **`UNMARKED` finding** — a startup failure nobody recorded is indistinguishable from a deleted archive |

Outcomes come from explicit markers, never from which logs happen to exist. Note the
`failed` row: a failure marker does not waive the log requirement, it only relaxes the
*set*. A run that failed must still have written the logs up to the failure.

---

## 5. Tests — 23, all passing

`test_verify.py` invokes `verify.py` as a **subprocess** and asserts on the **exit code**,
because the failure mode that matters is "exits 0 when it should not".

* **Complete set passes** (2 tests) — the one case that must be green.
* **Missing log is caught** (5) — missing `push.jsonl`, missing `move_to_pose.jsonl`,
  all missing, zero-byte file, explicit `--required` override.
* **Shared-dir defect** (3) — a log in the global dir does **not** satisfy the run and is
  named; absent-everywhere is MISSING not MISFILED; stale shared file is not MISFILED.
* **Outcomes** (5) — marked failure with partial logs passes; marked failure still requires
  its logs; startup failure reported with its marker; unmarked empty run is caught; missing
  run dir is caught.
* **Vacuous scan** (1) — scanning an empty tree exits 2.
* **Legacy layout** (1) — `<run>/skills` found and checked, missing log still caught.
* **Scan mode** (2), **JSON output** (1), **usage errors** (2).

Every test builds its own throwaway fixture in `tempfile`; no real evidence is touched.

---

## 6. Honest limits

* **`--profile push` asserts that a push run must have both `move_to_pose.jsonl` and
  `push.jsonl`.** That is the declared wiring (`push_server` moves the arm through
  `MoveToPose`), and it holds for all 6 T08 runs measured. It is a declaration, not a
  proof that every future push path will write both.
* **MISFILED ownership is hedged, not proven.** mtime ordering shows a shared file *could*
  belong to a run; it does not show which records do. Reading the mixed file to attribute
  records is a separate job and is not attempted.
* **The `pick_place` profile requires 8 logs.** Some legitimate runs may write fewer if a
  skill was never invoked (e.g. no carry on a table-only task). The manifest
  (`logs/expected_logs.txt`) is the intended override for those, and `--required` for
  one-offs.
* **This tool detects absence. It cannot detect a log that is present and wrong** — truncated
  mid-line, or from a different run copied in. Checksums and per-run request-id filtering
  would be the next step and are not here.
* No wall-clock/timestamp cross-check between a log's records and the run's own timing.

## 7. Files

```
verify.py        the checker (read-only; exits 0/1/2)
test_verify.py   23 tests, subprocess + exit-code based
README.md        this file
```
