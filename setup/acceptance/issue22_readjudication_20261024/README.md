# Issue #22 re-adjudication (2026-10-24)

Answers the sixth acceptance item of **#31** — _"重新核定 #22 的剩余工作：单物体
seam 已存在；批次 metadata 可标 S4，裸 pick_place_v1 不能全部硬映射为 S4"_. #31
was closed with that box unchecked, so the item is answered here from bytes that
were already in the tree.

**Verdict: #22 is a phantom issue.** Its four factual claims are not "partly
stale" — each one is contradicted by an artifact committed to this repository on
2026-10-01 or 2026-10-02, i.e. before the issue was posted on 2026-10-03. One of
its claims (the `pick_place_v1` hard-mapping warning) is correct and load-bearing,
and is preserved below as a checked invariant rather than thrown away with the rest.

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

> **Correction 2026-10-24 — the `replay_ok: True` above is a 2026-09-30 fact and
> no longer reproduces.** Regenerating the report from the same archived bytes on
> current `main` yields `REPORT: FAIL (2 episodes, 1 replay-dirty)`: step 4 of the
> S4 episode now diverges on `explanation` alone, because `5462124`
> (2026-10-23) reworded the PLACE-abort text to embed the typed skill code.
> `action`, `target`, `reason_code` and `confidence` still match exactly. The
> cell itself is still emitted, so C3 — the claim that S4 has no cell and is
> forced to FAIL — stands; what does not stand is any suggestion that the
> archived episode replays cleanly today. See
> [`../replay_drift_20261024/`](../replay_drift_20261024/README.md) for the
> measurement and the corrected invariant.

### C4 — "the runner runs cells sequentially … interleaving should land before M3 numbers are quoted"

**FALSE (already landed).** `setup/94_scenario_runner.py:230-231` builds the
schedule round-robin and `--dry-run` emits `order: round_robin`.

## What #22 got right — do not delete this along with the rest

`CELL_OF_SCENARIO` must **not** gain `'pick_place_v1': 'S4'`. Two code facts make
that a real constraint, not a preference:

- `task_fsm_server.py:333` hardcodes `scenario = 'pick_place_v1'` for **every**
  single-object run, whatever its target.
- `RunPickPlace.Goal` carries only `object_name / place_pose / motion_profile_id /
  skip_verify` — there is **no** scenario field to distinguish an S4 run from an
  ordinary reachable-target run.

A reachable-target single-object episode and an S4 episode are therefore
indistinguishable inside the episode file, so a hard mapping would relabel every
ordinary run as S4.

That is why S4's cell identity comes from **batch metadata**, on two levels:

1. `95_metrics_report.py:93` writes `benchmark_cell` from the batch row's
   `scenario` (the cell id) when `--batch` is supplied; and
2. `94_scenario_runner.py:310` calls `check_scenario_execution`, which for S4
   requires a step with `policy_output.action == 'PLACE'` and
   `executor_result.outcome == 1` — the label is **verified against the trace**,
   not asserted by the row.

The batch row is the authority; the episode cannot be.

## Residual gaps (real, and none of them is what #22 describes)

1. **No test covers the task path's recording.** `grep -rn "S4\|pick_place_v1"`
   over `src/flexcell/flexcell_skills/test/` and `setup/` returns nothing. If
   `_execute` stopped delegating tomorrow, the suite would stay green. This is
   the only gap here worth its own issue.
2. **Without `--batch`, an S4 episode lands in `dev/pick_place_v1`.** A
   consequence of (R3) above, not a defect, but undocumented — easy to
   rediscover as a bug.
3. **`95_metrics_report.py:56` reads `record.get('benchmark_cell')`, which has no
   producer.** The only write (`:93`) targets the in-memory record. The read path
   is dead; harmless, but it advertises a capability that does not exist.
4. **S3/S4 are n=1.** That is #31's `n≥50` freeze, not #22's scope.

## Recommendation

Close #22 with the C1–C4 refutations above and a pointer to this record; open one
narrow issue for residual 1 (regression coverage for task-path recording); note
residuals 2 and 3 in the closing comment instead of leaving them to be
rediscovered.

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
