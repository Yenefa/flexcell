# E-009 — first benchmark batch, SUPERSEDED (kept as defect evidence)

**Do not quote these numbers as benchmark results.** This was the first attempt
at the M3-seed batch on the new machine. Its **S7 cell is invalid**: the scenario
runner's `arm_inject` guard (`if payload:`) made the empty "clear" payload a
no-op, so the `exhaust_demo_v1:always` injection armed for S5 stayed live for
every later episode and pre-failed all 10 S7 episodes.

Authoritative results: [`../m3_seed_batch_20260929_clean/`](../m3_seed_batch_20260929_clean/).

## What is here

| file                          | what it is                                                                              |
| ----------------------------- | --------------------------------------------------------------------------------------- |
| `61_battery.out`              | Week-1.5 acceptance battery stdout: 5 GATE FAILs (4× `flood-clean`, `recovery_outcome`) |
| `94_batch.out`                | scenario-runner stdout, S1:20 S2:20 S5:20 S7:10                                         |
| `batch_20260929_001501.jsonl` | the runner's 70 row summary (this run)                                                  |
| `95_metrics_report.md`        | metrics report regenerated from the replay store over that batch                        |
| `95_report_stdout.out`        | the reporter's stdout for the same run                                                  |

## Results as measured (S7 column is invalid — see above)

- S1 16/20 = 0.80, Wilson95 [0.58, 0.92]
- S2 13/20 = 0.65, Wilson95 [0.43, 0.82]
- S5 0/20 SUCCEEDED (20/20 correctly FAILED, typed)
- **S7 0/10 = 0.00, Wilson95 [0.00, 0.28] — invalid (leftover injection)**
- `REPORT: PASS (70 episodes, 0 replay-dirty)`; runner verdict `FAIL (21)`

## Not in git

`pre_batch_reset.json` (the admin `reset` output used as the pre-batch canonical
world gate) is **not committed**: it is ~400 kB of the known
`gz.msgs.Pose` "No message class registered" traceback flood (see
[`docs/ISSUE_DRAFTS_20260929.md`](../../../docs/ISSUE_DRAFTS_20260929.md) issue B
— the same flood is already in the committed delivery-host artifacts, 963-1030
count). The machine-local copy lives with the workspace at
`setup/acceptance/m3_seed_batch_20260929/pre_batch_reset.json`; the verdict that
mattered is quoted in `docs/EXPERIMENTS.md` (E-009):

```
"ok": true, "scene_cleared": true,
"canonical target_box_a": "OK ['0.2200', '0.0000', '0.0175']",
"canonical target_box_b": "OK ['0.2000', '-0.1800', '0.0175']"
```
