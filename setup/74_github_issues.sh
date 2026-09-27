#!/usr/bin/env bash
# 74_github_issues.sh — create M2 labels, milestones and issues on Yenefa/flexcell
# Source of truth: docs/WEEK2_PREPARATION.md @ 4fccfb8 (ratified 2026-09-26)
set -u
REPO="Yenefa/flexcell"
OUT="F:/flexcell-stage/setup/74_issue_urls.txt"
: > "$OUT"

echo "== labels =="
gh label create m2 -R "$REPO" --color 1D76DB --description "M2 decision layer" --force || echo "label m2 failed"
gh label create design -R "$REPO" --color FBCA04 --description "design/ADR work" --force || echo "label design failed"
gh label create implementation -R "$REPO" --color 0E8A16 --description "code implementation" --force || echo "label impl failed"
gh label create benchmark -R "$REPO" --color D93F0B --description "benchmark harness/metrics" --force || echo "label bench failed"
gh label create blocked-external -R "$REPO" --color B60205 --description "blocked on external access/vendor" --force || echo "label ext failed"
gh label create hardening -R "$REPO" --color C5DEF5 --description "reliability hardening candidate" --force || echo "label hard failed"

echo "== milestones =="
gh api "repos/$REPO/milestones" -f title="M2.1 Decision Foundation" -f description="Ratified order steps 1-4: WorldState v2 freeze, DecisionPolicy interface, FSMPolicy (parity, priority raised), deterministic safety gate" || echo "milestone M2.1 failed"
gh api "repos/$REPO/milestones" -f title="M2.2 Replay & Benchmark Harness" -f description="Scenario runner, episode records, policy-input replay store, metrics reports, S7 perturbation track" || echo "milestone M2.2 failed"
gh api "repos/$REPO/milestones" -f title="M2.3 Policy Backends" -f description="JevPolicy (pluggable backends), LLMPolicy (deferred), HybridRouter with tau sweep" || echo "milestone M2.3 failed"

DOC="docs/WEEK2_PREPARATION.md @ 4fccfb8 (ratified 2026-09-26)"

echo "== issues =="
mk() { # mk <num> <title> <labels> <milestone>  (body on stdin)
  local num="$1" title="$2" labels="$3" ms="$4" url
  url=$(gh issue create -R "$REPO" --title "$title" --label "$labels" --milestone "$ms" --body-file -)
  if [ -n "$url" ]; then echo "$num | $url | $title" >> "$OUT"; echo "OK  $num $url"; else echo "FAIL $num $title"; fi
}

mk "M2.1-1" "[M2.1-1] Author ADR set from ratified Week-2 preparation (ADR-0001..0005)" "m2,design" "M2.1 Decision Foundation" <<'EOF'
Source of truth: `docs/WEEK2_PREPARATION.md @ 4fccfb8` (ratified 2026-09-26).

Author `docs/adr/`:

- ADR-0001 WorldState v2 additive schema + **versioned policy-input serialization** (`WorldStateSchemaVersion`, ratified ①)
- ADR-0002 DecisionPolicy seam in task executor + FSMPolicy trace-shape parity bar (ratified ②, priority raised)
- ADR-0003 JevBackend abstraction — TypeSafeBackend | LocalReproductionBackend, never vendor-bound (ratified ④)
- ADR-0004 Hybrid threshold as experimental variable, tau in {0.5, 0.7, 0.9} (ratified ⑤)
- ADR-0005 S7 perturbation track kept in primary (ratified ⑥)

**AC**: ADRs merged; each has Context / Decision / Consequences; cross-linked from WEEK2_PREPARATION.md.
EOF

mk "M2.1-2" "[M2.1-2] Freeze & implement WorldState v2 (additive) + versioned canonical serializer" "m2,implementation" "M2.1 Decision Foundation" <<'EOF'
Implement WEEK2_PREPARATION.md §3.3/§3.4:

- msgs: `schema_version`, `robot.gripper_position`, `objects[].klass`, `objects[].pose_age_s`, `zones[].occupied_by`, new `TaskContext` (+Assignment) assembled by the EXECUTOR
- zone geometry single-source (observe_server owns; task_fsm consumes from WorldState — kills the week1.yaml duplication)
- canonical serializer module with versioned envelope `{"WorldStateSchemaVersion": 2, ...}`; `notes[]` stripped from policy-facing bytes
- v1.5 fields UNCHANGED; skill behavior unchanged

**AC**: msgs build; serializer unit-tested with golden files; `flexcell start` health gate green; happy demo run indistinguishable from baseline `4fccfb8`.
EOF

mk "M2.1-3" "[M2.1-3] DecisionPolicy interface + Decision/TaskGoal/Constraints/TaskHistory types" "m2,design,implementation" "M2.1 Decision Foundation" <<'EOF'
Implement §2.2 as a pure-python package (proposed `flexcell_policy`, no rclpy dependency):

- policies operate on the **versioned canonical envelope** (not ROS msg objects); the executor bridges ROS msg <-> envelope
- ActionKind, TaskGoal, Constraints, Decision, TaskHistory, DecisionPolicy protocol (+ optional decide_distribution)
- policy contract rules 1-7 (§2.3) encoded as interface docs + validation helpers

**AC**: offline unit tests; FSMPolicy implementable against it without touching ROS.
EOF

mk "M2.1-4" "[M2.1-4] FSMPolicy + executor seam (decision_policy param, default=fsm) + trace-shape parity regression" "m2,implementation" "M2.1 Decision Foundation" <<'EOF'
PRIORITY RAISED (ratified ②): this is the baseline foundation.

- extract the demo-loop "what next" logic from task_fsm_server.py into FSMPolicy (§2.5)
- executor keeps: admission/mutex, _demo_call plumbing, cancellation, evidence, task_state
- new param `decision_policy: fsm|jev|llm|hybrid`, default `fsm` (zero behavior change)
- parity regression: RunDemo traces (fsm_trace strings, step records, error codes) shape-identical to baseline across happy / recovery(once) / exhaustion(always) scenarios

**AC**: parity suite green on cold-started stack; default lifecycle runs unchanged.
EOF

mk "M2.1-5" "[M2.1-5] Deterministic safety gate + invalid-decision accounting" "m2,implementation" "M2.1 Decision Foundation" <<'EOF'
Implement §2.6 validator before dispatch:

- action in allowed_actions; target exists; PICK => available & not carried (gz re-check, backend belief not trusted); PLACE => carried; world freshness gate; expected_world_revision stamped from observed revision; free text (explanation) can never reach a skill goal
- typed rejections recorded with full decision object; invalid-actions-per-1000 metric

**AC**: unit test with a planted out-of-contract proposal is deterministically rejected (issue #1 acceptance item); metric visible in episode records.
EOF

mk "M2.2-1" "[M2.2-1] Scenario runner + episode record + policy-input replay store" "m2,benchmark,implementation" "M2.2 Replay & Benchmark Harness" <<'EOF'
Implement §4.4:

- per-episode record: scenario_id, seed, initial_world_state, failure_injection_schedule, policy_input (+WorldStateSchemaVersion), policy_output, selected_action, executor_result, verifier_result, final_state, timestamps/latencies, env snapshot (load/uptime — delivery-acceptance lesson)
- offline replay runner: feed recorded state sequences to ANY policy without the robot
- scenarios S1-S5 defined from /flexcell/inject schedules (S7 separate issue)

**AC**: S1/S2 episodes recorded end-to-end and replayed offline for FSMPolicy.
EOF

mk "M2.2-2" "[M2.2-2] Benchmark harness + metrics report generator (cells A-D, B/C/D behind availability flags)" "m2,benchmark,implementation" "M2.2 Replay & Benchmark Harness" <<'EOF'
Implement §4:

- cells: A=FSM always; B/C/D behind backend-availability flags (ratified order: LLM deferred until this + interface exist)
- metrics 1-7 (§4.3): success rate (Wilson CI), recovery success, decision latency p50/p95/p99, LLM/Jev invocation count, cost, invalid actions/1000, calibration (ECE/reliability/Brier-when-distribution/risk-coverage)
- reports regenerate from the replay store; no hand-written PASS lines; pass gates per §4.5

**AC**: cell A end-to-end report from recorded episodes.
EOF

mk "M2.2-3" "[M2.2-3] S7 perturbation scenario builder (off-canonical placements)" "m2,benchmark" "M2.2 Replay & Benchmark Harness" <<'EOF'
Ratified ⑥: S7 stays in the PRIMARY benchmark.

- tooling: off-canonical initial object placements (gz set_pose) + scenario definitions + seeds
- design bar: perturbations must be hard enough that FSM sometimes fails — otherwise the track cannot discriminate policies
- rationale: the research question is whether hybrid decisioning wins when the environment changes beyond hand-coded range

**AC**: S7 scenario set + recorded episodes in the store.
EOF

mk "M2.3-1" "[M2.3-1] JevPolicy + pluggable JevBackend (TypeSafeBackend | LocalReproductionBackend)" "m2,implementation,blocked-external" "M2.3 Policy Backends" <<'EOF'
Ratified ④: backend-abstracted, never vendor-bound.

- `JevBackend` interface: spawn/classify/score + health + cost telemetry
- `TypeSafeBackend` (official SDK) — cloud NOT open to mainland China + our WSL network blackholes github; keep pluggable, do not block on it
- `LocalReproductionBackend` (APUS-style local model, MIT, GPU-optional, single-forward logits)
- OFFLINE spike of both on the replay store BEFORE any on-robot run: schema fit, distribution-vs-top1, latency p95, cost, calibration (supplement B — ECE/risk-coverage)

**AC**: backend interface merged; >=1 backend passes offline spike; calibration report exists.
EOF

mk "M2.3-2" "[M2.3-2] LLMPolicy (DEFERRED until interface + scenario runner + replay exist)" "m2,design" "M2.3 Policy Backends" <<'EOF'
Ratified ③: no LLM integration before M2.1 interface + M2.2 runner/replay are done.

- identical canonical bytes verbatim in a fixed prompt; structured output enforced; model/version/temp/seed recorded; token+cost logging
- provider/model pinned at start of this issue (earlier working assumption: DeepSeek via opencode zen gateway)

**AC**: same-interface parity; cost table from real calls.
EOF

mk "M2.3-3" "[M2.3-3] HybridRouter + threshold sweep tau in {0.5,0.7,0.9} + calibration report" "m2,benchmark,implementation" "M2.3 Policy Backends" <<'EOF'
Ratified ⑤⑥.

- escalation accounting; gate-checked on both tiers; FSM fallback on double failure
- tau swept as experimental variable (no fixed value until calibration data justifies promotion)
- report: risk-coverage + wrong-autonomous-decision rate vs tau across S1-S7; S7 is the differentiation track

**AC**: sweep report exists; escalation rate + success rate per tau documented.
EOF

mk "HARD-1" "[hardening] Carry servo observability: per-tick pin success/fail counters (touches FROZEN carry backend — needs explicit go)" "hardening" "" <<'EOF'
Delivery-acceptance evidence (att1/att2): servo GIL starvation produced rise~=0 grasp failures that were INVISIBLE in carry.jsonl (only start/stop events; set_pose failures surface only as rosout warns, and the vendor request() may fail without raising).

Proposal: per-tick pin success/fail counter + periodic summary line in carry.jsonl (and optionally TF-staleness counter).

CAUTION: carry backend is FROZEN (Week-1.5). Implement only with explicit chief go. Motivation for M2: benchmark episode diagnosis (distinguishing policy faults from servo starvation).
EOF

echo "== summary =="
cat "$OUT"
