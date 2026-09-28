# ADR-003: Orchestration Substrate — FSM as Control Arm, MTC as Treatment Arm

- **Status**: Proposed (drafted 2026-09-28 from the M2.3 audit P2-D1 + P2_DECISION_MEMO
  D1; **awaiting chief ratification** — per ROADMAP trigger T1 this MUST be ruled
  before M3 starts; it is not defaulting)
- **Context**: M2.3 full audit (审查报告 §5.2) found that the hand-written pick-place
  FSM manually replays the stage graph MoveIt Task Constructor (MTC) already provides
  (approach → grasp → lift → transit → place → retreat + planning-scene attach/detach)
  without parallel candidate search or cost-based solution selection. The question:
  replace the FSM orchestration layer with MTC, or keep it?
- **Deciders**: chief

## Context

Three facts frame the choice:

1. **The skill contracts are substrate-agnostic by design.** Every skill
   (Observe/Pick/Place/Verify/MoveToPose) is a typed ROS 2 action; the policy and the
   benchmark measure decisions, not planner internals. A different orchestrator behind
   the same actions changes nothing above the seam.
2. **The FSM is part of the research subject.** ADR-002 froze the decision layer so
   that policies are exchangeable; the orchestration substrate is the same kind of
   variable. A benchmark needs at least one control arm and one treatment arm — the
   frozen FSM _is_ the control arm.
3. **Switching now would invalidate all baselines.** Every parity baseline, skill
   contract, and acceptance battery assumes the current substrate; a mid-M2 rewrite
   buys no scientific information and destroys the regression net.

MTC is the ecosystem's contemporary answer for pick-and-place pipelines (MoveIt Pro
ships BT + MTC; its roadmap states it supersedes the legacy pick&place pipeline). The
audit's specific risk — "hand-written FSM is a manual replica of MTC's stage graph" —
is real for _engineering_ leverage (no parallel candidate search, no cost-ordered
solution selection, no planning-scene diff management), but it does not block the
_research_ question the project exists to answer.

## Decision (proposed)

1. **Keep the FSM orchestration layer through M2 and M3** as the deterministic
   control arm. No rewrite.
2. **An MTC-backed skill backend is evaluated as a treatment arm in M3**, behind the
   existing action contracts (a `place_server`/`pick_server` alternative
   implementation, not a new seam). It enters the benchmark like any other cell:
   same episodes, same metrics, same gates.
3. **A fresh literature/landscape pass (ROADMAP trigger T1) precedes the M3 launch**
   so the treatment-arm choice (MTC vs newer alternatives) is made against the then-
   current ecosystem, not this draft.
4. If a future ruling replaces the FSM outright, the replacement must reproduce the
   current action contracts byte-for-byte at the seam — the episode/replay store is
   the acceptance instrument.

## Consequences

- **Positive**: baselines survive; the decision-layer thesis gets its treatment arm
  "for free" at M3; no mid-M2 rewrite risk; the audit's "FSM reinvents MTC" concern is
  converted from a debt into a measured comparison.
- **Negative**: the hand-written FSM's engineering gaps (no parallel candidate search,
  no cost-based selection) remain until the M3 treatment arm exists; contact-grasp
  replacement (P2-D4) is unaffected by this ruling either way.
- **Neutral**: the传送 servo grasp mechanism stays exactly as declared in ADR-001 —
  this ADR rules on orchestration, not on the grasp mechanism.
