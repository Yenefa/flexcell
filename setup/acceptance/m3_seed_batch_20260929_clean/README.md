# E-009 — first official M3-seed benchmark batch (SUPERSEDED — DO NOT CITE)

> **These numbers are PROVISIONAL and must not be cited as a baseline.**
> Chief ruling 2026-09-29: the `gate_flood` zero-traceback gate had never been
> green, so no benchmark number may be cited until the T6 hardening lands and
> the batch is re-run. T6 (gate_flood + injection lifecycle + reset
> determinism) is now implemented and verified; the n>=20 re-run is the
> candidate for the **first M3 baseline**, and only after the chief freezes it
> do these numbers have standing. Kept for the audit trail of what the harness
> produced before the hardening.

Superseded by the T6 re-run. What it measured, for the record (policy =
`FSMPolicy`, headless, RTX 4060 laptop, 70 episodes, `REPORT: PASS (70
episodes, 0 replay-dirty)`):

| cell | scenario                        | success (metric 1)                                                         | Wilson 95% CI       | replay integrity |
| ---- | ------------------------------- | -------------------------------------------------------------------------- | ------------------- | ---------------- |
| S1   | canonical happy demo            | 18/20 = 0.90                                                               | [0.70, 0.97]        | 20/20 clean      |
| S2   | injected failure, first attempt | 8/20 = 0.40                                                                | [0.22, 0.61]        | 20/20 clean      |
| S5   | retry exhaustion                | 1/20 SUCCEEDED, so 19/20 correctly FAILED (typed `ERR_RECOVERY_EXHAUSTED`) | [0.01, 0.24]        | 20/20 clean      |
| S7   | off-canonical placement         | 6/10 = 0.60                                                                | [0.31, 0.83] (n<20) | 10/10 clean      |

**Why this run is not citable**, beyond the ruling:

1. it was produced with the `gate_flood` gate failing (the ~1000-line
   `gz.msgs.Pose` traceback flood in every reset artifact) - the measurement
   path itself was emitting errors;
2. one S5 episode succeeded because its `always` injection never armed, and the
   runner could not see that (now a `HARNESS_ERROR`, fail-closed);
3. the reset could not restore the canonical world after an abort-while-carrying
   (`scene_cleared: false`, `target_box_a: DRIFT`), so per-episode independence
   was not established.

All three are fixed and verified (see `docs/EXPERIMENTS.md` E-010).

## What is here

| file                                    | what it is                                                        |
| --------------------------------------- | ----------------------------------------------------------------- |
| `95_metrics_report.md`                  | the metrics report, verbatim (per-cell tables + per-episode rows) |
| `batch_merged.jsonl`                    | the merged 70-row batch definition the report is generated from   |
| `seg_S1_20.jsonl` ... `seg_S7_10.jsonl` | the four per-cell segment row files that merge into it            |
| `seg_*.out`                             | each segment's scenario-runner stdout                             |
| `94_batch.out`                          | the first (interrupted) single-invocation batch attempt           |

The batch ran as four independently resumable per-cell segments because the WSL
VM restarted twice mid-run and killed the detached runner. Partial attempts
remain in the episode store but appear in **no** row file, so they cannot enter
the report.

## Not run

S3 (absent from the runner), S4 (`RunPickPlace` records no episode and is off the
policy seam), the Day-2 battery, the independent referee, and any Jev/LLM arm -
see [`docs/ISSUE_DRAFTS_20260929.md`](../../../docs/ISSUE_DRAFTS_20260929.md).
