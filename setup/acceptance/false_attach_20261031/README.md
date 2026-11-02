# Declared false-attach window — local WSL run, 2026-10-31

One declared task (`infra/joint-false-attach-window.json`), executed once on the
local WSL stack (Ubuntu 24.04, ROS Jazzy, colcon merge-install), source tree at
`89f5a40` plus the injection point moved to 90 following samples (1.8 s), which is
the value frozen in `contracts/injection.parse_false_attach`.

This is **not** a CI run: GitHub Actions was refusing to start jobs when it was
taken. It is the same window script, the same manifest and the same gate that CI
runs; the difference is the host.

- window status: `FUNCTIONAL_WINDOW_PASS`
- trial status: `EXPECTED_FAILURE`, `expectation_met: true`
- task: `OUTCOME_FAILED` / `ERR_SKILL_FAILED`, trace `PICK_A(attempt=1):FAIL:ERR_INTERNAL`
- injection: 10 frames, 32.882–33.062 s sim, +0.03 m on world x
- guard fault: `measured relative pose exceeded follow limits`, peak 30.05 mm
- motion: cancelled with `motion_error_code 32` and a **confirmed** terminal
- PLACE dispatched: none; carry held for reconciliation, released by teardown
- runtime fingerprint: `79f37ed0d658314345debc7cdf2085e73a027ddf0e065a7f86ec241752919589`

Files:

- `window.json` — declared window result with the `false_attach_evidence` block
- `trial-result.json` — the trial's own result (identity, world/config hashes, task outcome)
- `carry.jsonl` — the carried session, including `false_attach_injected` with the exact frames
- `pick.jsonl` — the typed failure and the follow watch snapshot
- `params.yaml` — the resolved configuration for this run

Not archived here: rosbags, the 2 ms physics step log and the contact step log
(~14 MB per run). They stay on the machine that produced the run; the gate's
numbers in `window.json` are computed from them.
