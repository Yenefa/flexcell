# EXPERIMENTS — log

> One entry per experiment: purpose / scenario / configuration / result / evidence
> location. **Chat history is not experiment memory** — if a result is not recorded here
> (or linked from here), it did not happen. Benchmark (M3) numbers must regenerate from
> the replay store (#7/#8) — no hand-written PASS lines.

## Index

| ID    | Experiment                                             | Outcome      | Evidence                                                              |
| ----- | ------------------------------------------------------ | ------------ | --------------------------------------------------------------------- |
| E-001 | Day-1 environment verification                         | PASS         | acceptance/day1 (delivery host) + [DAY1_REPORT.md](../DAY1_REPORT.md) |
| E-002 | Day-2 MoveToPose acceptance                            | PASS 10/10   | acceptance/day2 + [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md)            |
| E-003 | Week-1 deterministic skills battery                    | PASS         | acceptance/week1                                                      |
| E-004 | Week-1.5 demo hardening — delivery acceptance (att3)   | PASS         | acceptance/week15/delivery_20260926/                                  |
| E-005 | Week-1.5 cold-start re-verification                    | PASS         | acceptance/week15/cs_20260926/                                        |
| E-006 | M2.3 audit remediation — runtime acceptance            | PASS (gated) | acceptance/sessions/ (FLEXCELL_STAGE) + ~/.ros/flexcell/referee.jsonl |
| E-007 | Scenario runner batch (S1×2 + S2 + S5), episode replay | PASS         | ~/.ros/flexcell/episodes/batch_20260928_051219.jsonl                  |
| E-008 | Metrics report over real store + S7 adaptation probe   | PASS         | ~/.ros/flexcell/episodes/batch_20260928_124615.jsonl                  |
| M3-*  | Hybrid Agent Benchmark (cells A-D × S1-S7)             | NOT RUN      | — (RFC #15; harness #7/#8/#9)                                         |

## Entries

### E-001 — Day-1 environment verification

- **Purpose**: prove the ROS 2 Jazzy + Gazebo Harmonic + MoveIt 2 + OpenMANIPULATOR-X
  stack end-to-end on the target machine.
- **Scenario**: Plan & Execute to a joint target; verify real motion in Gazebo physics.
- **Configuration**: WSL2 Ubuntu-24.04; Gazebo Harmonic 8.15.0; MoveIt 2; 6 colcon
  packages; 3 Gazebo controllers.
- **Result**: PLAN/EXECUTE error_code=1; MOTION_DETECTED=True; link poses move in
  physics; `/joint_states` consistent with the plan.
- **Evidence**: acceptance/day1/ (delivery host); [DAY1_REPORT.md](../DAY1_REPORT.md).

### E-002 — Day-2 MoveToPose acceptance

- **Purpose**: validate the agent-callable MoveToPose skill contract (typed request →
  MoveIt → Gazebo → measured result).
- **Scenario**: 10 cases — happy paths, timeout, cancel, IK-unreachable.
- **Result**: 10/10. Happy-path measured pose error 6-9 mm; timeout/cancel truly
  interrupt with `stop_confirmed`; IK fast-fail ≈ 1.06 s.
- **Evidence**: acceptance/day2/; [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md).

### E-003 — Week-1 deterministic skills

- **Purpose**: observe/pick/place/verify + strict FSM with measured-not-inherited
  success; typed negative paths.
- **Configuration**: conveyor-servo magnetic carry backend (see
  [ADR-001](ADR/ADR-001-simulation-manipulation-backend.md)); ground-truth truth loop.
- **Result**: full chain OBSERVE→PICK→PLACE→VERIFY SUCCEEDED with ground-truth error
  4.9-6.5 mm across runs; OBJECT_UNKNOWN / NOT_CARRIED / IK_UNREACHABLE /
  RESOURCE_BUSY all typed; Day-2 regression 10/10 (zero degradation).
- **Evidence**: acceptance/week1/ (18 artifacts).

### E-004 — Week-1.5 demo hardening (delivery acceptance, att3)

- **Purpose**: lifecycle CLI + strict health gate; dual-object A/B scenario; bounded
  recovery + fixed failure injection; repeatability.
- **Configuration**: recovery budget=1 (REOBSERVE+RETRY; recoverable = GRASP / MOTION /
  WORLD_STATE failures; otherwise typed abort); `/flexcell/inject`
  (`scenario:once\|always`); WorldState v1.5 frozen (`source=SIMULATION_GROUND_TRUTH`).
- **Result**: cold-machine run fully green — precheck 12 patterns all zero → start 34 s →
  happy demo 5.9/8.7 mm → double injection recovered → stop zero residue → poststop all
  zero. 5/5 repeats 2.5-10.6 mm; budget exhaustion → `ERR_RECOVERY_EXHAUSTED`; Day-2
  regression 10/10. att1/att2 servo-starvation failures were honestly caught (measured
  rise ≈ 0, zero false successes) — environment race, not code regression.
- **Evidence**: acceptance/week15/delivery_20260926/ (incl. `att1_att2/`).

### E-005 — Week-1.5 cold-start re-verification

- **Result**: run_id `week1_demo_v1-201be3fa`, 10.4/12.8 mm.
- **Evidence**: acceptance/week15/cs_20260926/.
- **Note**: `flexcell reset` may exit RC=139 (SIGSEGV) while reporting JSON `"ok":true`
  — vendor deserialize-thread/exit race; judge reset success by the JSON/health, not the
  exit code.

### E-006 — M2.3 audit remediation: runtime acceptance (2026-09-28)

- **Purpose**: verify the audit P0 fixes (ghost-trajectory guard, typed policy abort,
  cancel propagation, atomic admission) and the P1 acceptance infrastructure (colcon test,
  hard gates, independent referee, measured parity) under the live stack, headless.
- **Scenario**: happy demo + measured parity vs the frozen delivery baseline; referee ×5
  (independent gz-truth recompute of box_rise / zone_error cross-checked against the
  servers' jsonl); battery 61 (happy/recovery/exhaust/invalid) and battery 32 (10 cases)
  under hard gates; mutex probe (concurrent RunDemo+RunPickPlace); mid-pick cancel probe.
- **Configuration**: WSL2 Ubuntu-24.04 (headless: gz `-s`, no RViz), flexcell world;
  versioned `sessions/` dirs for artifacts.
- **Result**:
  - offline 86/86 (6 suites incl. new `test_runtime_guards`) and `colcon test` 86/0/0;
  - happy demo SUCCEEDED; measured parity vs `66_run_record_happy.jsonl` PASS;
  - exhaust → typed `ERR_RECOVERY_EXHAUSTED` (audit P1-2 acceptance); recovery →
    REOBSERVE+RETRY; invalid → typed negative (no catch-all wording);
  - mutex: second concurrent task → `ERR_RESOURCE_BUSY`; mid-pick cancel →
    `OUTCOME_CANCELED` + joint velocities ~0 after the stop;
  - battery 32: all 10 gates green (timeout/cancel details carry
    "preempted; stop confirmed"; MOTION_DETECTED=True);
  - referee: **zone_error agrees with the servers to ≤0.2 mm in every run** across all
    rounds; box_rise exposed a real mechanics finding — the teleport servo's set_pose
    requests succeed but the box reaches its pinned plateau seconds after the lift
    (carry engage unconfirmed; audit P2). The referee was re-scoped as an INTEGRITY
    check (overclaim / fake-grasp detection) with the catch-up delta logged as the D4
    monitoring metric; two INCONSISTENT verdicts in the final round were genuine demo
    failures (natural carry flake → typed BUDGET_EXHAUSTED policy abort, exercising the
    P0-2 path end-to-end) — detected, not masked.
- **Evidence**: `$FLEXCELL_STAGE/setup/acceptance/sessions/` (versioned session dirs);
  `~/.ros/flexcell/referee.jsonl`.
- **Open**: box_rise two-sided referee agreement is blocked by the carry-servo
  catch-up variance — contact grasping (D4) is the structural fix; the demo result
  detail prints `zone_%s_error_m` as 0.0000 while verify measures mm-scale (verify
  sampling moment to be checked in hardening).

### E-007 — Scenario runner batch: S1×2 + S2 + S5 with episode replay (2026-09-28)

- **Purpose**: close issue #7 — the scenario runner orchestrates reset → injection →
  demo/task → episode collection → offline policy-input replay → batch summary, with
  Wilson-CI success reporting (metric #1).
- **Configuration**: headless stack, flexcell world; batch `S1:2 S2:1 S5:1`;
  policy = FSMPolicy (replay of every recorded decision).
- **Result**: SCENARIO RUNNER PASS — S1 2/2 SUCCEEDED (CI95 [0.34, 1.00]), S2
  (injected first-attempt failure, recovered) 1/1 SUCCEEDED, S5 (retry exhaustion)
  FAILED as expected with the typed abort; **all 4 episodes replayed with 0 diverged
  decisions** (8/10/12/5 steps). Batch summary:
  `~/.ros/flexcell/episodes/batch_20260928_051219.jsonl`.
- **Evidence**: batch summary jsonl + the episode files it references.

### E-008 — Metrics report over the real store + S7 adaptation probe (2026-09-28)

- **Purpose**: close issues #8 (metrics report generator) and #9 (S7 perturbation
  builder).
- **#8**: `setup/95_metrics_report.py` regenerates every number from the replay store —
  per-cell success rate with Wilson 95% CI, decision-latency percentiles (metric 3),
  safety invalid-per-1000 (metric 6), and replay integrity per episode (planted-
  proposal records classified as gate evidence, excluded from the integrity
  denominator). Verified on the full store (21 episodes incl. dev iterations, kept in
  a separate `dev/*` bucket so they can never pollute a cell) and on the E-007 batch:
  both REPORT: PASS. Primitives in `contracts/metrics.py` (6 unit tests).
- **#9**: `setup/96_s7_perturb.py` — seeded off-canonical box placement inside the
  reachable band (geometry priors: ground plane, x∈[0.16,0.28], |y|≤0.24, ≥0.12 m
  separation, off zone centres), applied via the gz set_pose service; the runner
  attaches the schedule to the batch row. S7:2 batch → SCENARIO RUNNER PASS: both
  off-canonical demos SUCCEEDED (the deterministic baseline adapts to perturbed
  placement — the expected S7 outcome per ratified ⑥) with 0 diverged replay steps.
  Batch summary: `~/.ros/flexcell/episodes/batch_20260928_124615.jsonl`.
- **Evidence**: episode store + both batch summaries; report text in the issue
  comments.

## Evidence locations

- Delivery host: `F:\flexcell-stage\setup\acceptance\{day1,day2,week1,week15}\`
- Per-request structured logs: `~/.ros/flexcell/*.jsonl` (WSL; `evidence_id` per record)
- Lifecycle transcripts: flexcell CLI outputs (same acceptance dirs)
- Repo-side records: [DAY1_REPORT.md](../DAY1_REPORT.md),
  [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md)

> **Open (infra)**: acceptance evidence currently lives only on the delivery host. Decide
> whether key evidence bundles are copied into the repo (or an evidence branch) so the
> repository is fully self-contained — chief decision.
