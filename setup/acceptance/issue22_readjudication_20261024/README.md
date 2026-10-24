# Issue #22 re-adjudication (2026-10-24)

Answers the sixth acceptance item of **#31** — _"重新核定 #22 的剩余工作：单物体
seam 已存在；批次 metadata 可标 S4，裸 pick_place_v1 不能全部硬映射为 S4"_. #31
was closed with that box unchecked, so the item is answered here from bytes that
were already in the tree.

**Verdict: #22 is a phantom issue.** Its four factual claims are not "partly
stale" — each one is contradicted by an artifact committed to this repository on
2026-10-01 or 2026-10-02, i.e. before the issue was posted on 2026-10-03.
The re-adjudication also preserves a separate invariant: `pick_place_v1` must
not be hard-mapped to S4. The issue's proposed work suggested adding S3/S4
entries to `CELL_OF_SCENARIO`; it did not establish this warning itself.

## How the drift happened

The issue was drafted on 2026-09-29 against `main = 070aed6` (`docs/ISSUE_DRAFTS_20260929.md`
still records that base). At `070aed6` the claim was **true**:

| time (2026)          | event                                                                 | `_execute` (single-object path)                          |
| -------------------- | --------------------------------------------------------------------- | -------------------------------------------------------- |
| 09-26 `b2092257`     | `_execute` introduced                                                 | own body, no recorder / no `decide` / no episode write   |
| 09-28 `070aed6`      | the base the #22 draft was written against                            | same — the issue's `~257` line reference is exact        |
| 09-30                | new-machine mainline run: S3/S4 measured (`docs/MAINLINE_20260930.md`) | working tree already changed, not yet committed          |
| 10-01                | E-013 recorded on `main`: S3:1 and S4:1 both ran for real             | —                                                        |
| 10-02 `fd9bf72`      | checkpoint: `_execute` rewired **and** the `fsm_s3_s4` archive added in the same commit | fixed |
| 10-03                | #22 posted with the 09-29 body verbatim                               | already fixed for a day                                  |

So the draft was accurate, and the posting skipped re-verification against a
tree that had moved six days ahead. Nothing here says the original review was
careless — it says a draft-to-post gap across a refactor needs a recheck, which
is exactly what #31 item 6 asked for.

## Claim by claim

### C1 — "S4 runs through `RunPickPlace`, which records no episode and is not wired to the decision-policy seam"

**FALSE.** `_execute` is now a two-line delegator
(`setup/.../task_fsm_server.py:273-275`):

```python
def _execute(self, goal_handle):
    """Single-object tasks use the same policy/skill seam as RunDemo."""
    return self._execute_plan(goal_handle, single=True)
```

`EpisodeRecorder` (`:349`), `self._policy.decide(...)` (`:502`) and
`self._episodes.write(...)` (`:400`) all live in the shared `_execute_plan`, so
the single-object path and the demo path are the same code with one flag.

The byte-level refutation is `setup/acceptance/m3_online_v2_20260930/fsm_s3_s4/episodes/pick_place_v1_pick_place_v1-16d5aa87.json`,
committed in `fd9bf72`. It is a 4-step S4 episode in which **every step carries
`policy_input` and `policy_output`**, the `PLACE` step has
`executor_result.outcome = 1` (`IK pre-check failed: NO_IK_SOLUTION`), and
`final_state.error_code = 50`. That is precisely the artifact #22 says cannot exist.

### C2 — "S3 does not exist at all. There is no `S3` entry in `SCENARIOS`."

**FALSE.** `benchmark_protocol_v2.json` defines S3 =
`recovery_b_demo_v1` with injection `recovery_b_demo_v1@target_box_b:once`
(B-only, first attempt), and the same archive holds its episode
(`recovery_b_demo_v1_recovery_b_demo_v1-69d7d17f.json`, 10 steps).

### C3 — "S4 … makes any S4 batch report FAIL, and `95_metrics_report.py` has no cell for it"

**FALSE.** The archived `95_metrics_report.md` contains a `## Cell S4 … (n=1)`
section with `replay integrity 1/1 episodes clean` and ends
`REPORT: PASS (2 episodes, 0 replay-dirty)`. The corresponding batch row reads
`scenario: S4, outcome: FAILED, expected: FAILED, scenario_exercised: True,
replay_ok: True, replay_steps: 4, harness_error: None`.

> **Correction 2026-10-24 — the `replay_ok: True` above is the archived
> report's own historical result, not a claim that current FSM code replays every
> historical decision exactly.** Regenerating the report from the same archived
> bytes on current `main` yields `REPORT: FAIL (2 episodes, 1 replay-dirty)`:
> step 4 of the S4 episode now diverges on `explanation` alone, because `5462124`
> (2026-10-23) reworded the PLACE-abort text to embed the typed skill code.
> `action`, `target`, `reason_code` and `confidence` still match exactly. The
> cell itself is still emitted, and the S4 batch cell remains correctly assigned,
> so C3 — the claim that S4 has no cell and is forced to FAIL — stands; what does
> not stand is any suggestion that the archived episode replays cleanly today.
> The current-policy check below records the divergence in full; see
> [`../replay_drift_20261024/`](../replay_drift_20261024/README.md) for the
> measurement and the corrected invariant.

### C4 — "the runner runs cells sequentially … interleaving should land before M3 numbers are quoted"

**FALSE (already landed).** `setup/94_scenario_runner.py:230-231` builds the
schedule round-robin and `--dry-run` emits `order: round_robin`.

## Cell identity invariant retained by this re-adjudication

`CELL_OF_SCENARIO` must **not** gain `'pick_place_v1': 'S4'`. Two code facts make
that a real constraint, not a preference:

- `task_fsm_server.py:333` hardcodes `scenario = 'pick_place_v1'` for **every**
  single-object run, whatever its target.
- `RunPickPlace.Goal` carries only `object_name / place_pose / motion_profile_id /
  skip_verify` — there is **no** scenario field to distinguish an S4 run from an
  ordinary reachable-target run.

A reachable-target single-object episode and an S4 episode share the same
scenario id. Their observations, goals and results may differ, but the scenario
id alone cannot classify them; a hard mapping would relabel every ordinary run
as S4.

That is why S4's cell identity comes from **batch metadata**, on two levels:

1. `95_metrics_report.py:93` writes `benchmark_cell` from the batch row's
   `scenario` (the cell id) when `--batch` is supplied; and
2. `94_scenario_runner.py:310` calls `check_scenario_execution`, which for S4
   requires a step with `policy_output.action == 'PLACE'` and
   `executor_result.outcome == 1` — the label is **verified against the trace**,
   not asserted by the row.

The batch row is the authority; the episode cannot be.

## Follow-up correction (2026-10-24)

The first version of this record incorrectly claimed zero task-path tests and
a dead `benchmark_cell` read. The eleven-claim checker below did not check
either assertion, so its success did not validate them.

**Task recording already has execution tests.**
[`TestSingleTaskPolicySeam`](../../../src/flexcell/flexcell_skills/test/test_executor_integration.py)
calls the real `_execute` entry point and reads the episode written by the real
`EpisodeStore`, with skill replies supplied by the test harness. It covers:

- successful task, measured verifier result and FSM replay;
- S4 PLACE failure, policy ABORT and FSM replay;
- Jev S4 typed failure in both action result and episode;
- recoverable PICK failure followed by attempt two;
- skipped verification without inventing a measurement.

Four of these tests were already present in `fd9bf721fea44172fb70fa2fd12dd9486af0e094`,
alongside the seam change and native archive. The Jev test was added by
`be3abe8c4770e2ba71d114ee0581050a0edf2e50`. Both predate this record. These are
executor tests with ROS message classes and scripted skill replies, not Gazebo,
model inference or physical acceptance. No new zero-coverage issue is warranted.

**`benchmark_cell` is a live in-memory handoff.** `load_episodes(store, batch)`
loads an episode, adds the batch row's cell to that decoded record and returns
it; `episode_rows` calls `cell_of` on the same record. Its read therefore consumes
the loader's write. The original episode bytes stay unchanged. The field does
not need an on-disk producer.

[`test_metrics_cell_identity.py`](../../../src/flexcell/flexcell_skills/test/test_metrics_cell_identity.py)
now exercises that loader-to-report path, the four-step archived FSM S4 replay,
and the rule that unlabelled single-object tasks remain `dev/pick_place_v1`.
The reporter's usage text documents this behavior with and without `--batch`.
**Current-policy replay differs from the archived PASS.** Replaying the original
S4 bytes with `FSMPolicy` from `a7cd3cbf5bac747d72d4df002e5a3f743dfb2802`
produces three matching decisions and one mismatch. The recorded ABORT explanation
is `place failed (carried box is not retried)`; current code produces
`place failed (ERR_MOTION_FAILED, carried box is not retried)`. Action, target,
confidence and reason code match. Because replay compares the complete decision,
the current reporter correctly emits `REPORT: FAIL`, with the episode still in
Cell S4 when batch metadata is supplied. Without batch metadata it is a
`dev/pick_place_v1` replay failure. The tests preserve that distinction; the
episode and the old report are not rewritten to manufacture a current PASS.
This is a policy-version comparison, not a new robot execution or physical test.

**S3/S4 here remain n=1.** The archive supports the implementation claims above;
it does not complete a benchmark comparison or release the `n≥50` freeze.

## Recommendation

Use the C1–C4 evidence above when deciding #22's disposition. Do not create an
issue for absent task-path coverage or remove the live in-memory cell field.
Issue closure remains an explicit maintainer decision; this correction does not
change issue state or sampling eligibility.

## Verifying this document

```bash
python3 verify_issue22_claims.py      # 11 claims, read-only, stdlib only, no ROS
python3 selftest_verify_issue22.py    # 8 tamper cases; the checker must reject each
```

`verify_issue22_claims.py` exits `0` when every claim still holds, `1` when one
no longer does (the record must be updated — do not silence the checker), and `2`
when the archive is absent. The self-test requires all eight tampers to be
rejected, including one that hard-maps `pick_place_v1` to S4 (the R1 invariant)
and one that adds a scenario field to `RunPickPlace.Goal` (which would make R1's
premise obsolete and force a fresh re-adjudication).

The checker inspects source structure and historical artifacts; it does not run
the executor integration tests or verify all narrative and historical claims in
this document. Run the execution and reporting suites for those behavior checks.
