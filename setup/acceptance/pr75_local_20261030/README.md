# PR #75 local evidence

See `docs/PR75_LOCAL_CONTINUATION_20261030.md` for the result and its limits.

- `receipt.json`: source identity, original artifact hash, local test results,
  preserved untracked-path count and individual evidence file hashes.
- `probe.cpp` and `CMakeLists.txt`: standalone upstream point-sampler/KDL probe.
- `prepare.py` and `run.sh`: exact original local fixture preparation/invocation.
- `fixture.json` and `probe-params.yaml`: reconstructed geometry and model.
- `attempts.jsonl`, `stderr.log`, `summary.json`: one diagnostic execution,
  including controls and every fixed-attempt result.
- Build, static-scan, archive-replay and combined-test logs retain their actual
  outcomes. `build-offline.log` is the rejected existing-install attempt;
  `build-offline-isolated.log` is the successful isolated build.

There is no exact planning-scene snapshot. These records do not qualify Gazebo,
hardware, D3, or a production solver fix. Original failures remain rejected.
