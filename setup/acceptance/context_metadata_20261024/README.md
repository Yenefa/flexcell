# Observed backend context metadata (2026-10-24)

`102_mainline_runtime.sh` now writes manifest version 2 with separate fast/slow
runtime contexts instead of the historical hard-coded 8192. Each used,
unauthenticated arm gets one read-only models GET with a 2-second socket timeout
and a 64 KiB response limit. Missing, invalid or ambiguous runtime metadata stays
null with a status. Inactive and authenticated arms make no request; keys are
not read. This does not change policy decisions, motion or recovery budgets.

Stable context/selection fields and collector/deployer source hashes enter the
runtime fingerprint. The exact response, response SHA and observation time are
separate receipts, so a server's changing `created` field alone does not change
the fingerprint. A sole advertised model with a different request alias is
explicitly weaker than an exact model/alias match; it does not verify weights.

## Validation

- Local ROS Jazzy colcon: **290 tests / 0 errors / 0 failures / 0 skipped**.
  The 28 metadata cases exercise per-arm values, missing/invalid/ambiguous
  metadata, no authenticated/inactive requests, exact raw bytes, broken proxy,
  unavailable/oversized/truncated HTTP responses, and changing response metadata.
- Static scan: 36 source files, 0 problems; shell syntax and diff checks passed.
- One temporary **local CPU Qwen** server ran with `-c 12288`. The production
  manifest-generation Python fragment read **12288**, left the unused slow arm
  null, and generated a fingerprint that changes when the context changes.
  `fast_models.json` preserves the real response (`meta.n_ctx=12288`, distinct
  from its training limit 32768). No inference or robot goal was sent.
- The owned CPU process group exited and port 21881 stopped listening.
  The server exits 1 when the supervisor and process group receive termination;
  shutdown is checked by process-group absence and closed port, not a zero exit.
  A separate 90-second process deadline guarded the test. `receipt.json` records
  the exact command and shutdown checks; `local_probe.py` is the executed driver.

The live probe ran on staged source bytes over base 54e4b03. Their hashes match
commit 6d5acf3 exactly, verified in `validation.json`. The subsequent 262a655
follow-up catches HTTP protocol exceptions and adds a real truncated-chunk test;
its complete 290-test result is `pytest.xml` and `test-result.log`.
`test-result-before-fixture-fix.log` retains the initial test-fixture assertion
failure: a short Content-Length body produced JSONDecodeError with bounded
Python reads. The corrected fixture truncates an HTTP chunk and exercises the
actual IncompleteRead path. No robot run was involved in either test.

`deployment_fragment_only.json` is a serialization test, not a launched fleet:
its temporary model alias is Qwen and the task configuration's Clef label was
not instantiated. It cannot establish Clef, Hybrid, model replay or physical
acceptance. The prior five home-GPU robot episodes remain under
`../home_gpu_abort_20261024/` with their original fingerprint and 8192/16384
discrepancy unchanged. No new home GPU service was started. The original 176
historical episodes were not rerun; recovery from the offline execution desktop
is still pending. All earlier frozen evidence and the be3abe8 ZIP remain intact.

`MANIFEST.json` hashes every other file in this directory. All responses,
receipts and test outputs were copied byte for byte from the local run.
