# ADR-002: Runtime Decision Layer Boundary

- **Status**: Accepted (2026-09-27; M2.1 architecture freeze, chief-directed)
- **Context**: Week-2 preparation ratified (`docs/WEEK2_PREPARATION.md @ 4fccfb8`); RFC #14
  (decision layer architecture) and RFC #16 (WorldState v2 freeze) open
- **Deciders**: chief review; recorded through the project maintenance process

## Context

The current task executor (`task_fsm_server.py`, unchanged since `7956d63`) mixes three
concerns in one file: **which action comes next** (sequencing, recoverability
classification, retry budgeting), **how an action is dispatched** (action-client
plumbing, deadlines, cancellation, evidence), and **whether it worked** (recording
measured verdicts produced by the skills). Before WorldState v2 (#3), the
DecisionPolicy interface (#4), and the FSMPolicy extraction (#5) are implemented, the
boundary between the future Runtime Decision Layer, the Task Executor, and Verification
must be frozen so that the extraction has a legal contract and the parity regression
(#5) has an exact definition. This ADR is that freeze. The line-anchored audit of the
current file is Appendix A — it is an extraction map only; **no code was refactored**.

## Decision

The runtime splits into three responsibilities with one-way, typed information flow:

    Human Goal
        ↓  TaskGoal + Constraints (typed)
    Decision Layer            decides WHAT next: pure decide() → Decision
        ↓  Decision objects (the only channel down)
    Task Executor             decides HOW: gate → dispatch → evidence (deterministic)
        ↓  typed skill actions
    Skill Servers             perform; measurements happen here (skills own truth)
        ↑  typed results + measured verdicts
    Verification              independent ground truth; policy-blind

### Decision layer responsibility (WHAT to do next — models allowed here)

1. Maps `(WorldState, TaskGoal, Constraints, TaskHistory)` → `Decision(action, target,
confidence, reason_code, evidence_ref)`; nothing else in, nothing else out.
2. Chooses among the finite typed action set (observe / pick / place / verify / wait /
   abort + target) — issue #1's "bounded question".
3. Decides **when** to (re)observe, retry, wait, or abort; may use confidence as a
   routing signal (HybridRouter escalation).
4. **MUST NOT**: touch joints, trajectories, motion scaling, tolerances, budgets;
   perform IO or call skills; read logs or any channel outside the canonical snapshot;
   decide physical safety (issue #1 hard rule); emit actions outside the executor menu.

### Executor responsibility (HOW it is done — deterministic, no model)

1. Admission/mutex, cancellation semantics, per-skill deadlines and goal plumbing —
   the existing `_call_skill`/`_demo_call` mechanics, unchanged.
2. Assembles the canonical WorldState snapshot (+ TaskContext, v2) and enforces the
   `decide()` timeout with **FSM fallback** — a failing or silent policy degrades the
   system to today's behavior, never to silence.
3. **Safety gate**: deterministically validates every Decision before dispatch
   (allowed-action menu, target existence, carry re-check against physical evidence,
   world freshness, revision stamping, free-text ban). Invalid decisions are rejected
   typed and counted — never executed.
4. Budget **accounting**: the executor tracks recovery consumption and enforces the
   hard cap; a policy may spend less, never more.
5. Evidence chain: run_id → step records → skill evidence_ids; task-state topic;
   honest propagation of every measured verdict.
6. **MUST NOT**: choose actions (that is the policy's job), alter or second-guess
   measured verdicts, or dispatch on backend belief (`CarryState`) without independent
   physical confirmation.

### Verification responsibility (WHETHER it worked — measured, never inherited)

1. Truth lives in the skills, policy-blind: `verify_server` samples gz ground truth
   independently of who decided; pick's box-follow check (≥ 0.03 m) and place's drop
   check (0.06 m) run inside the skills as pre-conditions of honest results.
2. Verdicts are typed (`VERIFIED` / `MISMATCH` / `FAILED` + `position_error_m`);
   a MISMATCH is an honest result, not an error.
3. The executor records and propagates verdicts verbatim; the Decision Layer consumes
   them as typed history — never raw logs, never intentions.
4. Reset re-verification (±0.005 m) and the lifecycle health gate remain the
   episode-boundary truth anchors.

### Boundary invariants (the freeze)

- **B1 — Typed channels only**: state flows down as versioned canonical bytes
  (`WorldStateSchemaVersion`, ADR-001 principles extended by ratified ①); decisions
  flow down as typed `Decision` objects; results flow up as typed outcomes. No other
  channel exists.
- **B2 — Budget is a ceiling**: a decision can only consume recovery budget, never
  raise it; the executor enforces the cap.
- **B3 — Gate before dispatch**: no policy output reaches a skill goal without passing
  the safety gate; free text can never enter a machine path.
- **B4 — Policy-blind verification**: verification measures the world; it neither knows
  nor cares which policy decided.
- **B5 — Parity bar (ratified ②)**: with `decision_policy=fsm` (the default), behavior
  must be trace-shape-identical to the Week-1.5 baseline (fsm_trace strings, step
  records, error codes) across happy / recovery / exhaustion scenarios.
- **B6 — Replaceable parts**: swapping a policy, a Jev backend, or even the robot
  backend (ADR-001 rule 3) changes implementation only — the skill action contracts,
  the WorldState schema semantics, and this three-way split stay fixed.

## Consequences

- **Positive**: the FSMPolicy extraction (#5) gets an unambiguous seam and an exact
  regression definition; Jev/LLM/Hybrid (#10/#11/#12) and offline policy replay (#7)
  plug in without re-opening the boundary; benchmark results become attributable
  (decision quality measured inside a safe envelope, per issue #1).
- **Negative / accepted costs**: the executor's demo loop gets restructured once
  (mechanics preserved; covered by the B5 parity suite); policies are deliberately
  less "powerful" than a raw agent driving the robot — by design, that constraint IS
  the research frame; the gate adds a fixed validation step per decision (negligible
  next to second-scale skills).
- **Non-goals**: no grasp-physics work (ADR-001); no LLM integration (#11 deferred,
  ratified ③); no change to skill servers, Gazebo, or the carry backend.

## Appendix A — task_fsm_server.py extraction map (audit @ 8b188bc; no refactor)

File: `src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py` (539 lines,
unchanged since `7956d63`; anchors verified). Classification: which lines are
**decision** logic (moves to FSMPolicy), **execution** logic (stays in executor), or
**verification-adjacent** recording (executor records; measurement lives in skills).

| Lines                                           | Current code                                                                                                                                          | Class                                                  | Destination                                                 |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | ----------------------------------------------------------- |
| 392-393                                         | `plan = [('A', obj_a, 'zone_1'), ('B', obj_b, 'zone_2')]`                                                                                             | decision                                               | `TaskGoal.assignments` (goal input, from config)            |
| 394-516                                         | per-leg sequencing loop (OBSERVE → PICK → PLACE → VERIFY × 2 legs)                                                                                    | decision                                               | policy decide-loop (executor runs it per B1)                |
| 307-308                                         | `RECOVERABLE_PICK = {22, 23, 30}` (WORLD_STATE_UNAVAIL / GRASP_FAILED / MOTION_FAILED)                                                                | decision                                               | recoverability rule → FSMPolicy (constraint data)           |
| 410-451                                         | PICK retry loop: attempt ≤ budget, recoverable → REOBSERVE+RETRY (438), exhausted → `ERR_RECOVERY_EXHAUSTED` (431-437), non-recoverable → typed abort | decision (budget ceiling stays executor, B2)           | policy; executor enforces cap + records                     |
| 479-512                                         | VERIFY re-verify loop: MISMATCH → REOBSERVE+REVERIFY (507), exhausted → `ERR_RECOVERY_EXHAUSTED` (502-506)                                            | decision                                               | policy                                                      |
| 268-272                                         | `skip_verify` branch (typed goal flag; PLACE drop check already passed)                                                                               | decision-input                                         | `Constraints` (policy must respect)                         |
| 214-215, 228-230, 245-248, 274-276              | cancel-between-states → `CANCELED`                                                                                                                    | execution (invariant)                                  | executor (unchanged: cancellation is never a policy choice) |
| 71, 201-204, 385-389                            | admission mutex `_busy`/`_demo_busy` → `ERR_RESOURCE_BUSY`                                                                                            | execution                                              | executor                                                    |
| 134-165 (`_call_skill`), 310-335 (`_demo_call`) | action-client plumbing: wait 10s, goal-send 15s, result deadline, cancel-on-timeout                                                                   | execution                                              | executor (verbatim reuse)                                   |
| 216-218, 396-399                                | Observe goal construction (`refresh=True`)                                                                                                            | execution (the _why_ is the policy's OBSERVE decision) | dispatch table                                              |
| 231-234, 412-414                                | Pick goal construction (object, `motion_profile_id='demo_slow'`)                                                                                      | execution                                              | dispatch table; profile comes from `Constraints`            |
| 249-255, 454-461                                | Place goal construction (zone pose)                                                                                                                   | execution                                              | dispatch table                                              |
| 277-280                                         | Verify goal construction (tolerance from config)                                                                                                      | execution                                              | dispatch table                                              |
| 349-383                                         | `finish()`: outcome finalize, `succeed/abort/canceled`, `demo_runs.jsonl` write, task-state publish                                                   | execution (evidence)                                   | executor                                                    |
| 340-343                                         | run_id / scenario / evidence minting                                                                                                                  | execution (evidence)                                   | executor                                                    |
| 110-116, 129-132                                | latched `/flexcell/task_state` publisher                                                                                                              | execution                                              | executor                                                    |
| 156-158, 331-334                                | result-deadline enforcement + cancel sent                                                                                                             | execution                                              | executor                                                    |
| 160-163                                         | per-skill typed result recording (`outcome/error_code/detail`) into the request record                                                                | verification-adjacent                                  | executor (honest recording)                                 |
| 285-293                                         | VERIFY outcome → `object_at_place` / `final_position_error_m`                                                                                         | verification-adjacent                                  | executor (measurement is verify_server's)                   |
| 359-364                                         | zone verdicts `object_X_at_zone` / `zone_X_error_m` (NaN when unmeasured)                                                                             | verification-adjacent                                  | executor                                                    |
| 489-498                                         | verify step record with `position_error_m`                                                                                                            | verification-adjacent                                  | executor                                                    |
| —                                               | actual measurement: `verify_server` sampling; pick rise ≥ 0.03 m; place drop 0.06 m; reset ±0.005 m; health gate                                      | verification (skill/lifecycle side)                    | unchanged, outside this file                                |

Tally: ≈60 lines of genuine decision logic (plan, sequencing, recoverability, retry
budgeting) move behind the policy interface; ≈200 lines of dispatch/mutex/deadline
plumbing and ≈80 lines of evidence/state recording stay; measurement never enters this
file. Parity target (B5): the extracted FSMPolicy must reproduce these decision points
so that `fsm_trace`, step records and error codes remain shape-identical.
