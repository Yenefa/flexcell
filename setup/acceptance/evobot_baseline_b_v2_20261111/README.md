# Baseline B v2 — the agent plans, the harness records, nothing is graded here

**Date:** 2026-11-11 · **Arm:** B (runtime agent) · **Split:** train (not held-out)

## Status on the evidence ladder

| Level | Reached? | Why |
| --- | --- | --- |
| Designed | **yes** | this document + module docstrings |
| Implemented | **yes** | 5 modules under `runtime/planner/`, 1 harness, 1 checker |
| Unit Tested | **yes** | 54 tests, `benchmark/tests/test_baseline_b_v2.py` |
| Simulation Tested | **NO** | **no Gazebo run. Phase 1 only. This is deliberate.** |
| Independently Verified | **NO** | the independent evaluator has not seen a final state |
| Generalization Tested | **NO** | train split only; held-out numbers are not mine to report |

**Do not read the plan-level number below as a success rate.** It is a *planning*
measurement against `expected_goal`, not the evaluator's verdict on a world state.

## What was measured

| Quantity | Value | Source |
| --- | --- | --- |
| Instances planned | **17 / 18** | `plan_level_check.json` |
| Plan-level correct (of planned) | **17 / 17** | `plan_level_check.json` |
| Templates covered | **6 / 6** (T01–T06) | same |
| Total tokens | **14,643** | same |
| Model | `deepseek-flash`, temperature 0 | `agent_reply.json` |
| Credential route | `evobot_llm_key.sh` only | `key_source` field in every reply |

The one non-planned instance is analysed in `transient_retry.json`: an **empty model
response** after 2,625 tokens. Re-run 5×, it planned correctly **5/5** with **byte-
identical** moves. So it is a transport/model event, **not** a task the agent cannot
plan. The failed run is preserved in `failed_run_preserved/`, not deleted.

## Why this is not "Baseline B exists now"

It already did. `runtime/planner/agent_planner.py` + `prepare_baseline_b.py` were
committed in `9c59d5b2` ("Baseline B — the agent plans the task itself and passes
independent verification") and the T01 result is in
`setup/acceptance/evobot_t01_baseline_b_20261111/`. `docs/PROJECT_STATUS.md` says
otherwise because it was last edited at 01:42, **91 minutes after** that commit, and
the update did not reflect it. That is a documentation defect, reported to the Lead
rather than silently "fixed" by me.

## Four defects this work found and fixed

Each was **measured**, not suspected. All four are covered by regression tests.

### 1. The v1 observation was not a function of its input
`prepare_baseline_b.observation_from_spec` emitted colours from a module constant
`COLORS` and bin poses from `ZONE_LABEL`. Measured: mutating the task's own
`color` and `zones[0].pose` left the observation **byte-identical**. The agent was
reasoning about a hardcoded world. It matches the default scene today, which is why
nobody noticed. `public_observation.py` derives every field from the task.

### 2. The v1 observation offered bins the task never declared
Measured on **T02 and T03**: the spec declares `["zone_1"]`, v1 emitted
`["zone_1","zone_2"]`. A bin the task never offered is not an affordance; planning
into it produces a plan that cannot be graded, which then looks like a robot failure.

### 3. The v1 docstring claimed a safety assertion that does not exist
`prepare_baseline_b.py` says *"That is enforced by only touching the whitelisted
keys, and asserted at the end."* Measured: `"assert "` does not appear in the module
body at all. A comment claiming a check is worse than no comment — the next reader
stops looking. `public_observation.assert_public` now **raises** on any answer-bearing
key, and `LeakError` is proven to fire by mutation M1.

### 4. The v1 planner bypassed the LLM budget gate
`prepare_baseline_b.py` contains `from pilot.llm import Chat` and does **not**
contain `evobot_llm_key`. Measured with the env var removed:
`pilot.llm.setting("FLEXCELL_PILOT_API_KEY")` still returns a **35-byte key from the
Windows registry**. Any path reaching `pilot.llm.Chat()` can therefore spend money
without touching the gate — which is the exact incident the handoff document says the
user already held the project accountable for. `gated_chat.py` imports no part of
`pilot`, has no fallback branch, and a test parses its AST to prove it.

## Two bugs I introduced and then found

Recorded because the second one cost real money and both were caught by evidence,
not by review.

| Bug | How it surfaced | Fix |
| --- | --- | --- |
| Validator rejected a **correct** revisit plan (two sequential moves for one object) | a real 18-instance sweep: T06-train-seed1001 was scored a planning failure | one final destination = the **last** move naming the object, matching what the evaluator grades; both encodings now tested |
| A rejection discarded the model's raw reply | the sweep left "no JSON object in reply" with `raw_reply: null` — unfalsifiable | the exception carries `raw_reply` + `usage`; the harness writes them on failure |

The first bug was **also codified in a test** I had written
(`test_an_object_planned_to_finish_in_two_bins_is_rejected`). That test asserted my
wrong belief, passed, and would have kept the bug alive. It is replaced by
`test_two_sequential_moves_are_read_as_one_final_destination`, and the removal is
documented in the test file rather than silently deleted.

## The verifier can fail — proof, not assertion

`mutation_proof.json`, produced by `runtime/planner/verify_baseline_b.py`:

| # | Mutation | Property broke? |
| --- | --- | --- |
| M1 | leak guard disabled | **yes**, probe exit 1 |
| M2 | bin pose hardcoded | **yes**, probe exit 1 |
| M3 | gate refusal intercepted by an env-key fallback | **yes**, probe exit 1 |
| M4 | plan validation downgraded to a warning | **yes**, probe exit 1 |
| M5 | declared step budget ignored | **yes**, probe exit 1 |

A **control** run on the unmutated code passes first, so a probe that always failed
could not masquerade as five successes. `tracked_files_unmodified: true` confirms no
mutation leaked into the repo.

The verifier itself was then mutated (its M5 anchor removed): it reported
`every_check_is_proven_to_be_able_to_fail: false` and **exited 1**.

**A trap this file fell into once, recorded so it is not repeated:** the first version
of `verify_baseline_b.py` had a Python `SyntaxError`, printed nothing, and the shell
still reported `EXIT=0`. Three of the first five mutations were also not real (they
disabled one guard while a second guard still caught the case; they weakened a
condition that a later line overrode). The verifier reported them as **not caught**,
correctly. A "pass" with empty output is not a pass.

## What this does NOT show

- **No execution.** Nothing moved. No Gazebo, no robot, no final state.
- **No independent verdict.** `benchmark/evaluators/evaluate.py` has not run.
- **No generalisation.** Train split only.
- **`deepseek-flash` is not deterministic at temperature 0.** Two calls for the same
  task returned two different (both valid) encodings. A one-run-per-instance baseline
  is one sample of a distribution, and must be reported as such.
- **n is small** (18 instances, 3 seeds × 6 templates) and 17 usable.

## Reproduce

```bash
cd /mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
python3 -m pytest benchmark/tests/test_baseline_b_v2.py -q      # 54 passed
python3 runtime/planner/verify_baseline_b.py                     # exit 0, all 5 proven
python3 runtime/planner/gated_chat.py                            # gate preflight, 0 tokens
python3 runtime/planner/run_baseline_b.py --dry \
    benchmark/tasks/train/T01-train-seed1000.json --out /tmp/x   # 0 model calls
```

Spends money: `run_baseline_b.py` without `--dry`, one call per instance.
## The batch verifier also fails — four mutations

`verify.py` re-derives every number from the artefacts on disk, so a hand-edited
README cannot pass. Proven by mutating the evidence, running the verifier, and
restoring:

| # | Mutation | Verifier exit | Message |
| --- | --- | --- | --- |
| A | one plan's `clearance_m` set to 0.99 | **1** | `clearance 0.99 outside 0.05..0.25` |
| B | `expected placement: box_a to zone_1` injected into an observation | **1** | `observation leaks 'expected'` / `'placement'` |
| C | `key_source` changed to `direct file read` | **1** | `credential did not come from the budget gate` |
| D | `failed_run_preserved/` deleted | **1** | `the one failed run was not preserved as evidence` |
| — | restored | **0** | pass |

Mutation D is the one that matters most here. This project has been burned by a
"clean" record that was clean because the failures were never kept. The verifier
treats a missing failure artefact as a failure of the batch.

## A note on the empty-output trap, hit twice in this work

Two different verifiers in this batch exited `0` while printing nothing, and both
times the cause was a Python error the shell did not surface as non-zero through the
`wsl -d ... -- bash -lc` invocation. Both were caught only because "exit 0 with no
output" was treated as suspicious rather than as success. The final verification
pass captures stdout and stderr separately for this reason.
