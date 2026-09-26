# EXPERIMENTS — log

> One entry per experiment: purpose / scenario / configuration / result / evidence
> location. **Chat history is not experiment memory** — if a result is not recorded here
> (or linked from here), it did not happen. Benchmark (M3) numbers must regenerate from
> the replay store (#7/#8) — no hand-written PASS lines.

## Index

| ID    | Experiment                                           | Outcome    | Evidence                                                              |
| ----- | ---------------------------------------------------- | ---------- | --------------------------------------------------------------------- |
| E-001 | Day-1 environment verification                       | PASS       | acceptance/day1 (delivery host) + [DAY1_REPORT.md](../DAY1_REPORT.md) |
| E-002 | Day-2 MoveToPose acceptance                          | PASS 10/10 | acceptance/day2 + [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md)            |
| E-003 | Week-1 deterministic skills battery                  | PASS       | acceptance/week1                                                      |
| E-004 | Week-1.5 demo hardening — delivery acceptance (att3) | PASS       | acceptance/week15/delivery_20260926/                                  |
| E-005 | Week-1.5 cold-start re-verification                  | PASS       | acceptance/week15/cs_20260926/                                        |
| M3-*  | Hybrid Agent Benchmark (cells A-D × S1-S7)           | NOT RUN    | — (RFC #15; harness #7/#8/#9)                                         |

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

## Evidence locations

- Delivery host: `F:\flexcell-stage\setup\acceptance\{day1,day2,week1,week15}\`
- Per-request structured logs: `~/.ros/flexcell/*.jsonl` (WSL; `evidence_id` per record)
- Lifecycle transcripts: flexcell CLI outputs (same acceptance dirs)
- Repo-side records: [DAY1_REPORT.md](../DAY1_REPORT.md),
  [DAY2_MOVETOPOSE.md](DAY2_MOVETOPOSE.md)

> **Open (infra)**: acceptance evidence currently lives only on the delivery host. Decide
> whether key evidence bundles are copied into the repo (or an evidence branch) so the
> repository is fully self-contained — chief decision.
