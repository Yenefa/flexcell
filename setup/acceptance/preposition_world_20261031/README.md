# World-stationary pre-attach evidence

See `docs/PREPOSITION_WORLD_FRAME_20261031.md` for the repair, numbers and limits.
`raw-window.zip` contains all 60 files from the one declared window and its
preflight identity records. `receipt.json` hashes every member. `replay.json`
records the post-run re-derivation, including both raw and runtime world spreads.

Run `python3 setup/acceptance/preposition_world_20261031/verify.py` from a checkout.
This needs only Python's standard library and repository source; it calls no ROS
services and dispatches no robot actions. With ROS message packages available,
`--planner` additionally checks the exact planner CDR snapshots. The committed
source checkpoint is 19caa0199660c6a0d9d95af14620695dde0eedcf.

The old six-case red log, full test result and build/static logs are retained.
The first test invocation's merge-install layout error is preserved separately;
the corrected full invocation passed all 708 tests. `parity-counterexamples.json`
describes independent report-input gaps for a junior follow-up; it does not alter
the original #80 receipts. D3 stays NO_GO, no reliability claim or replacement run.
