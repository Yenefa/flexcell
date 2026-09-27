# P2 DECISIONS MEMO — awaiting the chief's ruling (M2.3 audit follow-up)

> 2026-09-28. Drafted by the remediation session from the M2.3 full audit
> (审查报告-全量进展与技术路线-20260928.md §7 P2 table). These are ROUTE
> decisions, deliberately NOT made unilaterally by the working session.
> Until ruled, M2.3 work proceeds on items that do not depend on them
> (P0 fixes, gates, referee, measured parity — all landed in this commit).

## D1 — Does the hand-written FSM orchestration layer get replaced by MTC?

**Question.** The audit notes our pick-place FSM manually replays the stage
graph MTC already provides (approach → grasp → lift → transit → place →
retreat + planning-scene attach/detach), without parallel candidate search or
cost-based solution selection.

**Recommendation: DO NOT switch now — but the default is not "never".**

- Switching invalidates every parity baseline and all skill contracts mid-M2;
  the decision-layer research question does not require it.
- The FSM orchestration layer IS part of the research subject: the whole
  point of `DecisionPolicy` is that the executor substrate is exchangeable.
  A second substrate (MTC-based skills behind the same actions) would be a
  _treatment arm_ for M3, not a rewrite.
- Required by the audit: whichever way we go, the ruling must be written down
  as **ADR-003** (orchestration substrate: FSM as control arm / MTC as
  treatment arm, or full replacement) before M3 starts.

**Proposal to ratify:** "FSM stays as the M2/M3 control arm; an MTC-backed
skill backend is evaluated as a treatment arm in M3, behind the existing
action contracts." → ADR-003.

## D2 — B5 (byte parity) vs M3 (policy comparison) — resolve the contradiction

**Question.** B5 demands byte-identical behavior when the policy changes —
which forbids the very thing M3 must measure (policy-quality differences).

**Recommendation: downgrade B5, split the two concerns (as the audit
proposes).**

- B5 becomes: **"the pipeline is unbroken when a policy is swapped"** —
  proven by trace-structure equality (normalized step labels), not by
  byte-equality of self-reported narration.
- M3 comparison metrics: **task success rate, FIRST-attempt success rate,
  recovery count, decision latency** — measured values, not trace strings.
- What landed in this commit already moves us there:
  `setup/91_measured_parity.py` compares measured zone errors + normalized
  step structure across runs (the old BYTE_PARITY compared fsm_trace strings
  and every captured artifact actually read PARITY: FAIL); attempt counters
  are normalized as executor-leg-local.
- The frozen Week-1.5 baseline files stay untouched (regression guard).

**Proposal to ratify:** B5 downgraded as above; amendment recorded in
ADR-002 addendum + ROADMAP M3 entry.

## D3 — Does M2.3 (replay harness / benchmark / S7) proceed as planned?

**Recommendation: yes, but episode recorder FIRST** (issue #7 tail), because
without it "first-attempt success rate" is unmeasurable and every M3 metric
degenerates to re-reading self-reported logs. Order: episode recorder →
scenario runner + replay store (#7) → safety gate (#6) → benchmark harness
(#8) → S7 (#9) → Jev (#10) stays deferred per ratified ③.

## D4 — Exit condition for the teleport-servo grasp

**Question.** The magnetic carry servo is a declared declarative compromise;
the entire M2/M3 evidence stack rests on it (biggest single dependency).

**Recommendation: keep it through M2, with an explicit, written exit
trigger:** whichever comes first —

1. M3 produces its first benchmark batch (contact grasping becomes a
   treatment-arm requirement), or
2. a first real-hardware bring-up is scheduled (contact physics becomes
   unavoidable), or
3. fake-grasp rate (box-did-not-follow) exceeds 10% of picks across a
   20-pick window (mechanism no longer reliable enough to underwrite
   claims).
   Each future HANDOFF entry reports the current fake-grasp rate so the trigger
   is monitored, not discovered.
