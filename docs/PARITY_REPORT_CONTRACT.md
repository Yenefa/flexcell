# Carry comparison report inputs

`scripts/parity_report.py` is an offline, read-only comparison. Supply at least
two `window.json` paths with distinct carry backends, the same skill backend and
declaration, and all five declared cases in order. Every window must have
`FUNCTIONAL_WINDOW_PASS`. Only the budget-exhaustion case may have
`EXPECTED_FAILURE / OUTCOME_FAILED / ERR_RECOVERY_EXHAUSTED`.

Success metrics are joined to the actual `skills/verify.jsonl` rows. Both object
verifications are required for the dual-object case. Errors must be finite,
nonnegative numbers; boolean values are rejected. The positive, consistent
tolerance comes from these rows: the archived runs use **0.06 m**. The report
does not add a 12 mm gate or substitute a tolerance for missing data. Negative
cases have no placement metric; absent optional attempt logs are reported as
unknown rather than zero.

Each recorded run path must resolve uniquely to its original directory, a
`trial-XX/run-ID` directory beside the window, or the sealed flat `run-ID`
layout. Missing or ambiguous directories and missing/damaged verification rows
are rejected. A transported CI artifact must retain the trial directory.

The tracked historical window summaries alone are intentionally insufficient.
For a replay of the original three MTC windows, extract the sealed source copy
to a temporary directory, leaving the frozen evidence untouched:

```bash
replay_dir=$(mktemp -d)
tar -xf setup/acceptance/native_portable_20261101/legacy-review-source.tar \
  -C "$replay_dir" setup/acceptance/legacy_parity_20261031
python3 scripts/parity_report.py \
  "$replay_dir/setup/acceptance/legacy_parity_20261031/teleport/window.json" \
  "$replay_dir/setup/acceptance/legacy_parity_20261031/velocity_servo/window.json" \
  "$replay_dir/setup/acceptance/legacy_parity_20261031/detachable_joint/window.json"
rm -rf -- "$replay_dir"
```

`CARRY_BACKEND_PARITY_PASS` describes the supplied bounded windows. It does not
qualify the default backend, establish a success rate, close #59, or change D3
`NO_GO`. MTC and legacy skill results must be compared in separate reports.
