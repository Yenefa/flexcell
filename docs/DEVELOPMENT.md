# DEVELOPMENT — execution calendar & maintenance policy

> Milestone/task-based, no fixed dates. This file is the operational layer between
> [ROADMAP.md](ROADMAP.md) (long-term) and Issues (per-work tracking). Update it as work
> progresses — checkboxes here mirror issue states.

## How work is tracked

- **Issues** carry the work: RFC issues (architecture of record — discussion and sign-off
  before implementation) and implementation issues (fine-grained, grouped under
  sub-milestones M2.1 / M2.2 / M2.3).
- **Milestones** group issues: M1 (done) → M2 umbrella (M2.1/M2.2/M2.3) → M3.
- **GitHub Project board** "FlexCell Development Board": Roadmap view (grouped by
  milestone) + Current Sprint (active items only).
  _(Board setup pending: the CLI token needs the `project` scope — run
  `gh auth refresh -s project -s read:project`, then create the board with the two views.)_
- Design of record for M2: [WEEK2_PREPARATION.md](WEEK2_PREPARATION.md) (ratified §0.5).
- Experiments and their evidence: [EXPERIMENTS.md](EXPERIMENTS.md).
- Architecture-level decisions: [ADR/](ADR/).

## M1 — Deterministic Workcell Baseline ✅ DONE

Day 1 → Day 2 → Week 1 → Week 1.5 all accepted (see [EXPERIMENTS.md](EXPERIMENTS.md)
entries E-001..E-005). The Week-1.5 delivery baseline `7956d63` is the frozen behavior
reference for all future parity claims.

## M2 — Runtime Decision Foundation 🔵 CURRENT

Ratified order: **WorldState → Decision Interface → FSMPolicy → Scenario Replay → Jev →
LLM**. LLM is explicitly deferred (③) until interface + scenario runner + replay exist.

Checklist (ratified order — check off as issues close):

- [x] WorldState v2 freeze + versioned canonical serializer — #3 (contract RFC #16)
- [x] DecisionPolicy interface + Decision/TaskGoal/Constraints/TaskHistory types — #4 (RFC #14)
- [x] FSMPolicy + executor seam (`decision_policy: fsm|jev|llm|hybrid`, default=fsm) + trace-shape parity — #5
- [x] Deterministic safety gate + invalid-decision accounting — #6
      (`contracts/safety_gate.py` + executor wiring + planted-proposal test hook;
      2026-09-28)
- [x] Episode record + policy-input replay store + scenario runner — #7
      (`contracts/episode.py` + executor recorder + `setup/93_replay.py`
      offline replay + `setup/94_scenario_runner.py` S1/S2/S4/S5 orchestration
      with Wilson-CI batch summaries; 2026-09-28)
- [x] Benchmark harness + metrics report generator — #8
      (`contracts/metrics.py` primitives + `setup/95_metrics_report.py`
      regenerating every number from the replay store; 2026-09-28)
- [x] S7 perturbation scenario builder — #9
      (`setup/96_s7_perturb.py` seeded off-canonical placement + runner
      integration; S7:2 batch green; 2026-09-28)
- [ ] JevPolicy + pluggable JevBackend (TypeSafeBackend | LocalReproductionBackend) — #10
- [ ] LLMPolicy — #11 (**DEFERRED ③** — do not start before the four items above exist)
- [ ] HybridRouter + threshold sweep τ∈{0.5,0.7,0.9} + calibration report — #12
- [x] ADR set from the ratified Week-2 preparation — #2 (ADR-001 simulation
      backend, ADR-002 decision-layer boundary + **Accepted B5 addendum**;
      plus ADR-003 orchestration substrate — ratified with three amendments
      2026-09-28: FSM = reference/control arm, MTC = alternative orchestration
      behind the same skill seam, M3 entry gate)

**Definition of done for M2**: every benchmark cell can run offline on the replay store;
FSMPolicy trace parity is proven; the safety gate deterministically rejects planted
out-of-contract proposals; Week-1.5 acceptance battery is still green.

## M3 — Hybrid Agent Benchmark ⚪ FUTURE

RFC #15 holds the research question, cells, metrics, scenario suite and pass/fail gates.
Start condition: M2 definition-of-done met. Results are recorded in
[EXPERIMENTS.md](EXPERIMENTS.md) and must regenerate from the replay store.

## Maintenance policy (every change, from now on)

**Before coding:**

- Which Issue does this belong to? (none → open one, or extend an existing RFC)
- Does it require a new ADR? (architecture-level choices always do)
- Do ROADMAP.md / DEVELOPMENT.md need an update once this lands?

**After coding:**

- Update the Issue: progress, evidence, close with a summary; link the commit.
- Record experiment results in EXPERIMENTS.md with their evidence location.
- Keep ROADMAP.md / DEVELOPMENT.md consistent with what actually shipped.

**Avoid:**

- Important decisions that live only in chat
- Undocumented architecture changes
- Orphan experiments (no Issue, no evidence, no docs)

## Document map

| Doc                                                       | Role                                                |
| --------------------------------------------------------- | --------------------------------------------------- |
| README.md                                                 | project front page + roadmap snapshot               |
| docs/ROADMAP.md                                           | long-term phases & milestones                       |
| docs/DEVELOPMENT.md                                       | this file — execution calendar + maintenance policy |
| docs/ARCHITECTURE.md                                      | system architecture (current vs target)             |
| docs/EXPERIMENTS.md                                       | experiment log with evidence locations              |
| docs/ADR/                                                 | architecture decision records                       |
| docs/WEEK2_PREPARATION.md                                 | ratified Week-2 design (source of record for M2)    |
| docs/ORIGIN.md · docs/DAY2_MOVETOPOSE.md · DAY1_REPORT.md | historical record (preserve)                        |
