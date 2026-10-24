# Fixed smoke-window admission evidence — 2026-10-24

Source and scope are recorded in `verification.json`. A fresh local ROS Jazzy
build of interfaces/skills passed; colcon reports **330 tests, zero errors,
failures and skips**. Static scan: 36 source files, zero problems. The 46 new
window tests and actual CLI comparison use synthetic records and stop before
ROS/model transport. No robot or model process was started.

`comparison.json` compares the actual CLI at base 071fa14 with the repaired
entrypoint. A ten-row pool (eight successes/two failures) and a five-row window
with duplicated native evidence reach the old dispatch boundary. The new CLI
rejects both with exit 2 before that boundary. A complete positive control
reaches both boundaries. Raw logs and clearly named synthetic inputs are kept.
Native-looking JSON under `synthetic_*` is fixture data, not robot episodes.

To regenerate the comparison into a fresh temporary directory from this checkout:

```bash
PYTHONPATH=src/flexcell/flexcell_skills python3 \
  setup/acceptance/fixed_smoke_window_20261024/compare_cli.py
```

The driver defaults to a new temporary output directory and leaves this frozen
archive intact. `FLEXCELL_SMOKE_REPO` and `FLEXCELL_SMOKE_OUT` can select another
checkout and a new output directory. It imports the test fixtures and needs
pytest, but does not import a ROS client or start a model service.

`historical_inventory.json` independently recomputes the three E-021 baseline
counts (19/20,18/20,17/20), the ten pooled attempts (8 SUCCEEDED/2 FAILED), and
A/B result-field presence. It preserves all 60 baseline native references and
exact filename matches in this checkout and the laptop's local episode store:
none were found in those checked roots. This is not a claim of global loss.
Raw historical summaries are untouched. Missing native recovery/model replay,
full M3 and n>=50 remain pending/frozen; this repair does not qualify history.

`MANIFEST.json` hashes all other archived files. Responses, fixtures, logs and
JUnit were copied byte for byte from the executed local checks. See the
[behavior and compatibility note](../../../docs/FIXED_SMOKE_WINDOW_20261024.md)
for plan format, relocation and qualification limits.
