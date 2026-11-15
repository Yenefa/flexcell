# Run-log retention and explicit missing-log checks (#231)

Offline tooling, no robot and no pytest. This note records what a run directory must
contain, what happens when it does not, and how to reproduce both claims on this
machine.

## Why this exists

A run that cannot explain itself afterwards is not evidence. The defect is recorded
in [FACT_STATE_20261112.md](FACT_STATE_20261112.md) (addendum, 2026-11-12, "Missing
evidence"): the T08 push probe's push.jsonl was not retained, because the legacy
launch profile had no push_server log_dir entry and the container fallback directory
was not mounted. The omission surfaced only while reading results, not at the moment
it happened.

An auditor that prints "ok" for whatever it happens to find cannot catch that, because
it reports success by silence. This tool inverts the default: the required inventory
is data in [config/run_log_required.json](../config/run_log_required.json), every
missing item is named, and any missing item is a non-zero exit.

Retention only: no motion code, no task definition, no evaluator and no threshold is
touched (#231 scope).

## What is checked

The inventory is phase-aware, because demanding an episode record from a run that
never launched would train operators to ignore the report.

| Phase | How it is derived | Typical required items |
| --- | --- | --- |
| success | task.out RESULT has outcome 0 and error_code 0 | task result, episode records, decision log, FSM log, per-stage skill jsonl, verdict.json |
| failure | it started (RESULT present but not successful, or task-layer evidence exists) and did not report success | the same plus failure_evidence.json and a crash/failure detail |
| startup_failure | nothing shows it reached the task layer | launch.out plus a crash/failure detail, and nothing task-level |

The items themselves (ids, kinds, reasons, phases) are declared in
`config/run_log_required.json`; the code only implements the kinds. Adding a newly
required log is a config edit.

Product references, so the inventory is not invented:

* episode records - `src/flexcell/flexcell_skills/flexcell_skills/contracts/episode.py`
  (`EpisodeStore` writes one JSON per episode; the audit requires
  `EpisodeSchemaVersion` plus a `steps` list).
* decision records and skill jsonl - `JsonlLog` in
  `src/flexcell/flexcell_skills/flexcell_skills/common.py`, used by
  `task_fsm.jsonl`, `demo_runs.jsonl`, `decisions.jsonl`, `observe.jsonl`,
  `move_to_pose.jsonl`, `pick.jsonl`, `place.jsonl`, `carry.jsonl`, `push.jsonl` and
  `verify.jsonl`.
* failure record - `runtime/recovery/recovery_driver.py` writes
  `failure_evidence.json`.
* crash detail - `crash_detail()` in `common.py`; it is retained either as its own
  file, in `failure_evidence.json:detail`, in the RESULT detail, or as launcher
  markers.
* stage evidence - `completed_stage_ids` in the RESULT and the FSM/demo log, plus
  stage tokens in the detail such as `PUSH_A`. A stage token `PUSH_A` requires
  `push.jsonl`; this is the rule that would have caught the T08 omission.

## Output directory, pointers and exit codes

* Every invocation writes a NEW directory: `<out-root>/run_log_audit_<UTC>-<n>/`
  containing exactly one file, `audit.json`. Two audits of the same run never
  overwrite each other; `--out` is refused when the directory already exists.
* The audited run directory is read-only. Existing raw failure data is recorded as
  `{path, bytes, sha256}` in `audit.json` - a pointer plus a hash, never a copy, so a
  large archive costs a hash pass instead of a duplicate.
* A missing item prints `MISSING: <run-id>/<path> (<reason>)`.
* Exit codes: `0` every required item present, `1` at least one missing, `2` usage or
  configuration error (missing run directory, directory that is not a run, unreadable
  or invalid config, or an output directory that already exists). There is no code
  path that reports success without having checked the inventory.

## Usage

    python scripts/run_log_audit.py <run-dir>                 # one run
    python scripts/run_log_audit.py <parent-of-runs>          # every run below it
    python scripts/run_log_audit.py <run-dir> --out-root artifacts/run_log_audit
    python scripts/run_log_audit.py <run-dir> --out /tmp/audit-one-run
    python scripts/run_log_audit.py <run-dir> --config /tmp/my-inventory.json

`artifacts/` is git-ignored, so the default output root never enters the repository.

## Self-verification (no ROS, no simulator, no pytest)

All fixtures are synthetic and built by the test itself in a temporary directory.

    python scripts/test_run_log_audit.py

Captured output on this Windows host (Python 3.12, no pytest, no ROS):

    test_batch_mode_reports_every_run_and_fails_if_any_is_incomplete ... ok
    test_complete_runs_pass_and_startup_demands_no_task_level_logs ... ok
    ...
    Ran 13 tests in 1.6s
    OK

    exit code: 0

The 13 cases cover the three required fixture families twice - complete (the
phase-aware inventory must accept them) and with items removed (exact missing set and
exit 1) - plus output-directory policy, pointer/sha256 behaviour, jsonl and episode
validation, batch mode, and usage/config errors.

A manual demonstration of the two outcomes, using the same fixture builder:

    $ python scripts/run_log_audit.py <tmp>/runs
    run run_exec_failure phase=failure required=8 missing=0
    run run_normal phase=success required=7 missing=0
    run run_startup_failure phase=startup_failure required=2 missing=0
    audit summary: 3 run(s), 3 passed, 0 failed, 0 missing item(s)
    pointers: 19 file(s) recorded with sha256, 0 bytes copied
    exit code: 0

    $ # delete run_normal/push.jsonl, then repeat
    run run_normal phase=success required=7 missing=1
    MISSING: run_normal/push.jsonl (the run's stage evidence names this skill but its jsonl was not retained (stage PUSH_A))
    audit summary: 3 run(s), 2 passed, 1 failed, 1 missing item(s)
    exit code: 1

## Limits (stated, not hidden)

* Validated on synthetic fixtures only. This checkout is sparse: it has no
  `setup/acceptance` archive, so no real archived run was audited here. Pointing the
  tool at a real archive is the lead's WSL-side step.
* The item paths are run-directory-relative and were chosen from the source that
  writes the logs, not from a real archive. If the retained archive keeps a log under
  `logs/` or `sim/`, that is one config edit per item - the code does not need to
  change, which is why the inventory is data.
* Not wired into any experiment runner or CI workflow: that would edit `setup/`,
  `experiments/` or `.github/`, which this work package deliberately does not touch.
  Until it is wired in, the audit is a check an operator or the lead runs, not a gate.
* The phase classifier is intentionally conservative: an unparseable or missing
  RESULT is a `failure`, never a success, so the missing `task_result` is reported.
* A single trailing unparseable jsonl line is tolerated (a crash can cut the last
  write) and that tolerance is recorded in `audit.json`; any other unparseable line is
  a missing item.
