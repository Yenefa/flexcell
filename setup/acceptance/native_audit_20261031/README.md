# Native audit lifetime capsule

2026-11-01 portability correction: the historical receipt intentionally retains
its mixed LF/CRLF checkout hashes. The verifier now binds exactly four Python text
sources to the already sealed canonical runtime map, accepting only CRLF-pair to
LF transport conversions and independently checking the historical observations.
The old receipt, source binding and ZIP are unchanged. Fresh Git LF snapshots now
pass on both Windows and Linux; the earlier Linux result used the Windows mount.
Proof and counterexample: `setup/acceptance/native_portable_20261101/`.

Two real local five-cycle windows, one per version, and the unchanged historical
CI failure. No ROS services or simulator are started by the replay:

```bash
python3 setup/acceptance/native_audit_20261031/verify.py
```

Expected: `NATIVE_AUDIT_LIFETIME_REPLAY_PASS`, historical `STOPPED`, patched source
metadata `INVALID_TRAILING_CR`, and `default_admission=NO_GO`.

- `raw-evidence.zip`: 114 byte-verified members, 24,031,905 bytes, containing both
  complete windows (raw physics/contact, rosbag, health/reset, native events,
  diagnostics, installed/mapped identity) and the exact historical CI ZIP.
- `receipt.json`: whole/member SHA-256, source/gate hashes, test counts and process
  preservation results. `receipt-before-source-binding.json` preserves the initial
  metadata assumption that strict replay rejected.
- `source-binding.json`: explicit supplement for a CRLF sidecar error. Raw runtime
  metadata is unchanged; all 209 recorded source hashes match Git 3328693 and the
  original Git tar. Exact raw CR/CRLF and source-tree digest are checked.
- `replay-windows.json` / `replay-linux.json`: successful portable replays, including
  the metadata defect.
- `native-reader-pause-repro.py`: deterministic in-memory timing counterexample;
  proves a possible observer mechanism, not the historical CI pause source.

Baseline and patched worker source files and diagnostic runners are inside
`scripts/` in the ZIP. The wrapper differs only in frozen source path. The original
Windows stage-export script in the ZIP intentionally retains the sidecar-writing
bug as executed. Future sidecars must be written with explicit LF bytes.

The original first-test-harness IndexError log and corrected red/green logs are
retained in `preflight/`; no production fix is inferred from the invalid first red
test. The 707 passing Python tests emitted three existing inference-budget fork
warnings. Four C++ cases and the 40-file static scan also passed.

Raw ZIP SHA-256:
`eed67b533957848cdc64dda090a4911a66344e81d7a7655269da6edc45591446`

Only the completed-audit heap lifetime is fixed. The historical CI cause remains
UNKNOWN, and neither a latency guarantee nor D3 admission follows from two local
passing windows. See `docs/NATIVE_AUDIT_LIFETIME_20261031.md` for measurements and
the exact qualification limits.
