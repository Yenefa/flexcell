# ADR-003: Orchestration Substrate — FSM as Reference Control Arm, MTC as Treatment Arm

> Evidence correction (2026-09-30): the checkmarks below record the original
> entry-gate claim, not a fully verified M3 comparison. S3/S4 and precise
> decision timing were missing from the historical batches; their code paths
> have now executed online. Distinct model endpoints are deployed and a real
> LLM single-object task completed; calibration and MTC remain pending.
> Servo is retained by user instruction; contact-grasp quality is outside
> current claims. See [mainline implementation](../MAINLINE_20260930.md).

- **Status**: Accepted (2026-09-28; chief review — **ratified with three amendments**,
  folded into the Decision below: ① FSM defined as reference/control arm, not assumed
  optimal; ② MTC repositioned from "skill backend" to "alternative orchestration
  implementation behind the same skill seam"; ③ M3 entry gate added. Ratification also
  endorsed the ADR-002 B5 addendum in the same review.)
- **Context**: M2.3 full audit (审查报告 §5.2, P2-D1) found the hand-written pick-place
  FSM replays the stage graph MoveIt Task Constructor (MTC) already provides
  (approach → grasp → lift → transit → place → retreat + planning-scene attach/detach)
  without parallel candidate search or cost-based solution selection. Ruling question:
  replace the FSM orchestration layer with MTC, or keep it?
- **Deciders**: chief review 2026-09-28 (this document is the ruling of record)

## Context

Three facts frame the choice:

1. **The skill contracts are substrate-agnostic by design.** Every skill
   (Observe/Pick/Place/Verify/MoveToPose) is a typed ROS 2 action; the policy and the
   benchmark measure decisions, not planner internals. A different orchestrator behind
   the same actions changes nothing above the seam.
2. **The FSM is part of the research subject.** ADR-002 froze the decision layer so
   that policies are exchangeable; the orchestration substrate is the same kind of
   variable. A benchmark needs at least one control arm and one treatment arm.
3. **Switching now would invalidate all baselines.** Every parity baseline, skill
   contract, and acceptance battery assumes the current substrate; a mid-M2 rewrite
   buys no scientific information and destroys the regression net. The observed
   repeated pick/verify/recovery cycles are the deterministic baseline doing its job —
   research-subject behavior, not a defect to migrate away from.

## Decision

**1. FSM = deterministic reference implementation (control arm) — NOT the assumed
optimal orchestration substrate.**

> FSM is retained as the deterministic reference implementation and benchmark control
> arm, not as the assumed optimal orchestration substrate.

No claim is made (in either direction) that the FSM is better engineering than MTC;
it is the frozen control condition of the experiment. Its known engineering gaps (no
parallel candidate search, no cost-ordered solution selection, no planning-scene diff
management) are recorded, not defended.

**2. MTC = an alternative orchestration implementation behind the same skill seam —
never a second decision layer.**

MTC is not a motion planner bolted inside `pick_server`; it is a task pipeline
(stages → solutions → cost ranking → execution) and therefore sits at the
orchestration layer. The substrate comparison is layered as:

    control arm                        treatment arm
    -------------------------          ---------------------------------
    DecisionPolicy (FSM/…)             DecisionPolicy (FSM/…)
        ↓ Decision                         ↓ Decision
    Task Executor                      Task Executor
        ↓ skill actions                    ↓ skill actions
    PickSkill (hand-written FSM)       PickSkill (MTC implementation)
        ↓                                  ↓
    MoveIt                             MTC
                                           ↓
                                       MoveIt

MTC stays strictly BELOW the Task Executor boundary: it never sees `Decision`
objects, never reads WorldState, never touches the action menu — ADR-002's
three-way split and B1-B6 invariants hold unchanged. The orchestration substrate
joins ADR-002 B6's replaceable-parts list; **the orchestration substrate is
replaceable, but the evaluation seam is frozen.**

**3. M3 entry gate — the treatment arm only enters after the measurement
infrastructure exists.**

M2 completion is the prerequisite (all landed 2026-09-26→28):

- ✅ WorldState v2 + canonical serialization (#3)
- ✅ DecisionPolicy seam + FSMPolicy (#4/#5)
- ✅ SkillResult v2 + post-condition verifier (#20)
- ✅ Episode record + policy-input replay store (#7)
- ✅ Scenario runner S1-S5 + metrics report (#7/#8) + S7 perturbation builder (#9)
- ✅ Deterministic safety gate with invalid-decision accounting (#6)

This gate exists to block the classic robotics death spiral: "see new framework →
start migrating" before the instrument that would measure whether the migration was
worth it is even built.

**4. A fresh literature/landscape pass (ROADMAP trigger T1) precedes the M3 launch**,
so the treatment-arm choice (MTC vs newer alternatives) is made against the
then-current ecosystem, not this document.

**5. Replacement contract**: if a future ruling replaces the FSM outright, the
replacement must reproduce the current action contracts at the seam — the
episode/replay store is the acceptance instrument.

**6. Treatment-arm metrics (M3)**: the §4.3 set (task success rate, first-attempt
success rate, recovery count, decision latency) **plus substrate-specific additions**:
planning time, collision-avoidance events, episode latency. Both arms run the same
episodes (S1-S7), same verifier, same WorldState bytes.

**Known comparison caveat (honest, carried until P2-D4 resolves)**: the teleport-servo
grasp flattens part of MTC's advantage (its strongest stages — approach/grasp/lift —
assume real contact). The M3 substrate comparison is valid for orchestration-level
differences; contact-grasp quality differences only become measurable after the D4
exit condition lands contact grasping.

## Consequences

- **Positive**: baselines survive; the "did we reinvent a solved problem?" question is
  answered honestly (partly yes, in engineering; no, in research) and converted into a
  measured M3 comparison; no mid-M2 rewrite risk; the entry gate blocks premature
  migration.
- **Negative**: the FSM's engineering gaps stay until the M3 treatment arm exists;
  until contact grasping (D4) the substrate comparison under-measures grasp-stage
  differences.
- **Neutral**: the teleport-servo grasp mechanism stays exactly as declared in
  ADR-001 — this ADR rules on orchestration, not on the grasp mechanism.
