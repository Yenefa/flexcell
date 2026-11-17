# Evidence index (competition)

Raw, immutable records for the status claims. Nothing here is rewritten; each item keeps its
original identity (hashes/receipts) even if the runtime later changes.

- In-repo measured evidence: `setup/acceptance/` (day1, day2, week1, week15, trusted_sim_*,
  recorder_replay_*, e021_*, grasp_*, native_five_*, joint_*, issue121_closure_*).
- Frozen cloud copy referenced by issues: `/workspace/flexcell-119-results` (+ `.zip`),
  `/home/ros/run118` for #114, etc. These are pointers; binaries are not committed.
- CI results: the GitHub Actions runs named in [DELIVERY_STATUS.md](../DELIVERY_STATUS.md).
- 团队协作留痕（2026-11-17）：[contribution_20261117.md](contribution_20261117.md)
  — issue #246 与 #245 从认领到 PR 的可核查记录（认领留言、9 个提交、PR #264 / #267、验证与判定）。

Rules: never delete or edit a sealed record to make a new claim pass; add a new record and a new
fingerprint instead.
