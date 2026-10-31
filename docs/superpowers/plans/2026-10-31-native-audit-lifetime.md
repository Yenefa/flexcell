# Native Audit Lifetime Implementation Plan

> Execute inline with the executing-plans workflow; use an independent reviewer at
> the code/evidence boundary. The user has authorized implementation and remote PR.

**Goal:** Release completed audit JSON graphs before the next native live cycle.

**Architecture:** A scoped audit returns the existing summary. Failure receipts add
clock/stack/follower context without retrying or changing any decision.

**Tech Stack:** Python 3.12, pytest, ROS 2 Jazzy, Gazebo Harmonic; existing pinned
native/install snapshot reused only after source/installed byte identity checks.

## 1. Red tests

- [ ] Add `test_completed_audit_rows_are_released_before_next_live_cycle` to
  `src/flexcell/flexcell_skills/test/test_native_cycle_window.py`. Run the actual
  worker through five mocked transport/follower cycles, track only parsed audit
  dictionaries using weak references, and assert the next cycle holds zero:

  ```python
  assert module.worker(tmp_path, 'empty', declaration) == 0
  assert alive_at_cycle_start == [0, 0, 0, 0, 0]
  ```

- [ ] Extend the real unready-guard failure test to require a positive failure
  clock, original error/traceback and empty reader table diagnostics.
- [ ] Run these tests against 11de825 code; save failures separately.

## 2. Minimal patch

- [ ] Move the existing `complete`, duplicate/contact checks and `verify_cycle`
  block into `audit_cycle(out, cycle, declaration)`. Replace the block with:

  ```python
  cycle['evidence'] = audit_cycle(out, cycle, declaration)
  ```

- [ ] Add read-only `Follower.diagnostic()` with timestamp, latest row per stream,
  common tick and file offsets/sizes. Snapshot failures become diagnostic errors.
- [ ] In worker exception handling preserve `repr(exc)`, `traceback.format_exc()`,
  `time.monotonic_ns()` and the follower diagnostic. Keep STOPPED/return-code logic.
- [ ] Run targeted red tests, all existing native gate tests, the complete offline
  suite and `python3 setup/82_undefined_attr_check.py src/flexcell`. Commit code.

## 3. Runtime and delivery

- [ ] Add an immutable native declaration linked to CI failure and the diagnostic
  baseline, with every numerical limit and world/config hash unchanged. Commit it.
- [ ] Export the committed source into a fresh WSL stage. Verify installed Python,
  launch and mapped native hashes. Never build or normalize the old dirty tree.
- [ ] Run exactly one five-cycle diagnostic window. Retain raw data, all GC/reader
  measurements, health/reset/cleanup, and source/script/declaration identities.
- [ ] Replay baseline and patched raw gates offline, compare active pauses, preserve
  the CI ZIP, and package a complete independently hashed evidence capsule.
- [ ] Request independent review, fix substantive findings and repeat only affected
  checks. Update HANDOFF and diary, push a stacked PR based on #81. Keep known CI
  account-startup failure separate from local test results and D3 admission.
