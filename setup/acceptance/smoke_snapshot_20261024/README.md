# Snapshot compatibility follow-up — 2026-10-24

`105_snapshot_smoke.py` preserves exact-byte planned qualification windows in
addition to its existing original/presentation exports. Legacy files receive no
invented plan. `receipt.json` records the tested source commit/hashes.

The two new filesystem integration cases cover the planned and legacy paths,
unchanged source/native/plan bytes, legacy presentation re-export, a second
snapshot after removing the original directory, and verification after another
relocation. Records are synthetic test fixtures, with zero model/robot calls
and no external service started.

The complete local ROS Jazzy suite passed **332 tests, 0 errors, 0 failures,
0 skipped**; static scan: 36 files, 0 problems. Raw test log and JUnit bytes are
preserved. The earlier 330-test gate evidence remains unchanged under
`../fixed_smoke_window_20261024/`. This is filesystem/contract verification,
not a new live smoke or historical qualification. Missing episode recovery,
model replay and the existing large-sample freeze are unchanged.
