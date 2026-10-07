# Hybrid batch provenance repair — 2026-10-07

Refs: [#8](https://github.com/Yenefa/flexcell/issues/8),
[#12](https://github.com/Yenefa/flexcell/issues/12), E-021 next actions and
[school handoff](SCHOOL_AGENT_TAKEOVER_20261005.md). Source base:
`a9b6a6255d91a568e44eea555ecb33f7e0d7d49f` (merged PR #27).

## Defect and resulting behavior

A hybrid episode with a successful slow-model decision could pass the old
routing audit even when its fast proposal was skipped or absent. All its
decisions could therefore come from the slow model with **zero fast calls and
zero fast tokens**, while the harness reported valid hybrid provenance.

The repair rejects a model-driven episode without a real fast proposal. The
existing harness-error path preserves its raw Episode, records the audit
failure and stops subsequent dispatch. It also audits the whole hybrid batch:
each row must have a passing episode audit, the expected calibration and runtime
fingerprint, valid counts and no non-bootstrap FSM fallback. A batch must contain
positive fast calls and measured tokens. One valid episode cannot conceal a
later episode without a fast arm.

The fast model may run and escalate **every** decision to the slow model. That
valid operating point still passes; the gate does not require fast selection.
It checks recorded provenance, not a live model-server health endpoint or proof
against deliberately forged evidence. HybridRouter fallback semantics and robot
execution are unchanged.

Before dispatch, the runner requires the deployment fingerprint and fast
model/weight/calibration identity. Before baseline dispatch, it rechecks the
qualifying smoke rows against the frozen deployment. Older smoke without the
new calibration field cannot grant qualification. FSM/LLM/Jev runs keep their
existing paths; only hybrid accepts `--deployment`.

## Evidence and compatibility

Batch audits are stored in:

```text
~/.ros/flexcell/episodes/batch_audits/<batch_id>.json
```

The sidecar carries the batch ID, summary path, protocol SHA, stage and aggregate
routing audit. It is outside the root-level `*.json` episode enumeration used by
existing runner/replay/metrics readers. Episode JSON and completed batch JSONL
rows remain intact. A harness error fails qualification; it is not relabeled as
a physical policy failure or silently included in the success denominator.

The same source change requires a new deployment fingerprint and fresh online
qualification after merge. Historical E-019/E-020/E-021 outcomes are retained
under their original identities. This PR does not re-score their raw robot
episodes or erase their physical failures.

## Offline verification — E-023

Evidence: [`setup/acceptance/hybrid_batch_gate_20261007/`](../setup/acceptance/hybrid_batch_gate_20261007/).

- `reproduction.json`: synthetic inputs, old/new episode reports and new batch
  reports. Skipped and missing fast proposals passed on the base revision and
  fail after repair. Real fast proposals with only slow selections still pass.
  Fixture identities and token counts are synthetic, not live measurements.
- `pytest.xml`, `pytest.log`: **194 passed, zero errors/failures/skips**, including
  **22 new regressions**. Eight existing routing-audit tests also remain green.
  New tests exercise the real runner's stop, sidecar and baseline-preflight
  paths using an offline episode-producing transport.
- `static_scan.log`: **35 source files, zero missing attributes**.
- `verification.json`: source base, source SHA-256 hashes, exact pytest/scanner
  commands and the eleven excluded ROS-dependent test files.

Dedicated rerun from the repo root, in an environment with pytest:

```bash
PYTHONPATH=src/flexcell/flexcell_skills python3 -m pytest -o addopts= -q \
  src/flexcell/flexcell_skills/test/test_batch_routing.py \
  src/flexcell/flexcell_skills/test/test_routing_audit.py
python3 setup/82_undefined_attr_check.py src/flexcell
```

The cloud environment has no ROS/Gazebo. Live model calls, pinned model replay,
robot-host smoke and runtime acceptance are **NOT_RUN** here. ROS CI verifies
build/test compatibility separately; it does not qualify Gazebo or the model
backend. Full M3 acceptance and n≥50 remain frozen. Next online work is a
new-fingerprint smoke plus the required acceptance battery, alongside diagnosis
of the cross-arm grasp failure.

See the requested [current architecture and development planning diagrams](ARCHITECTURE_AND_PLAN_20261007.md).
