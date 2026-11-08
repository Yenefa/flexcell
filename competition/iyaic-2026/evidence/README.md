# Evidence index (competition)

Raw, immutable records for the status claims. Nothing here is rewritten; each item keeps its
original identity (hashes/receipts) even if the runtime later changes.

- In-repo measured evidence: `setup/acceptance/` (day1, day2, week1, week15, trusted_sim_*,
  recorder_replay_*, e021_*, grasp_*, native_five_*, joint_*, issue121_closure_*).
- Frozen cloud copy referenced by issues: `/workspace/flexcell-119-results` (+ `.zip`),
  `/home/ros/run118` for #114, etc. These are pointers; binaries are not committed.
- CI results: the GitHub Actions runs named in [DELIVERY_STATUS.md](../DELIVERY_STATUS.md).

Rules: never delete or edit a sealed record to make a new claim pass; add a new record and a new
fingerprint instead.
