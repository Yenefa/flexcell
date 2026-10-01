# Evidence interpretation

This directory records mainline repair work and measured failures. It is not a
statistical benchmark. Protocol v2 and each runtime fingerprint stay separate.

- `batches/` and `episodes/` preserve original raw files. Paths inside batch rows
  still name the original on-host store. Copied episodes have the same bytes.
  `late_episode_correlation.json` adds a goal-UUID correlation for the client's
  timeout without rewriting that batch's HARNESS_ERROR.
- `structured_logs/` preserves selected original JSONL payloads. The selection
  rule and lower timestamp bound are recorded in `log_selection.json`.
- `api_direct_probe.json` contains two JSONL records despite its original suffix;
  neither is a successful authenticated model completion.
- `prior_manifest_check.json` and `git_evidence_manifest_check.json` are earlier
  incomplete checks. The former skipped the list-shaped E-014 file mapping;
  the latter only checked E-013/E-015. `archived_evidence_bytecheck.json` supersedes
  both: it actually checks all 263 E-014, 81 E-013 and 110 E-015 items, in both Git
  blobs and working-tree bytes, against the original manifests.
- `line_endings.json` lists attempted physical source normalization before the
  two historical setup logs were restored byte-for-byte. No acceptance archive
  should be renormalized. The original explicit binary/EOL attribute rules are
  retained and raw setup logs are also exempt from Git text conversion.
- `counterfactual.json` evaluates Qwen on historical recorded DeepSeek inputs;
  it does not verify replay of the historical remote model.
- `fixtures/` and `replay_fixture_one/` contain derived model input fixtures with
  no physical execution. `same_model_replay.json` / `same_model_metrics.md` record
  a real FAIL, not a robot behavior result. Frozen source checks verify both the
  archive hashes and identity after importing that archive, with no extra calls.
- `jev_calibration_collection.json` is the unchanged raw collection. The separate
  deployment profile `jev_calibration.json` records migration from whole-module
  hashing to the unchanged prompt function AST; source and collection hashes
  remain in that profile. The label is FSM action agreement, not grasp success.
- `source_snapshot.zip` captures implementation at source HEAD 525097d;
  `frozen_replay_source.zip` captures the earlier actual offline model evaluation
  implementation. Diagnostics subsequently added to the live LLM policy change
  its source identity, so the two archives intentionally differ.
- The final runtime source check verifies 30 installed Python files against the
  final deployment metadata. The earlier successful FSM S1 does not certify the
  final runtime fingerprint. Final checks were reset, health and stale-cache
  injection, with explicit process exit codes.
- The native callback controls consist of six short subscriber subprocesses,
  600 callbacks total. They do not reproduce the full historical admin teardown
  workload. Neither gate_flood nor reset SIGSEGV root is declared resolved.
- Full skills tests are contracts/control-flow tests; the real crashing child
  verifies the admin terminal-exit contract. The later five carry snapshot tests
  include two additional bounded reply-loss cases. Passing mocks do not prove
  physics reliability.
- API keys are not stored here. Backend profile files contain endpoint settings
  and external credential-file paths only. Unknown API outcomes remain charged
  at their conservative reservation in `budget_snapshot.json`.
