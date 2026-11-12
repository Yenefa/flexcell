# EvoBot next development plan — 2026-11-12

Decision base: local `fa08d8fe`, upstream runtime `30fa2066`.
Authority: North Star Mission, Master Goal and
`setup/acceptance/evobot_lead_t08_calib_20261112/AUTHORITY_SCOPE.md`.
Current capability remains **CALIBRATION_UNSUPPORTED; L4 NOT ACQUIRED**.
Public stage tracker: [#235](https://github.com/Yenefa/flexcell/issues/235).

## Research order and gates

| Order | Outcome sought | Evidence required to advance |
| --- | --- | --- |
| 1 — now | Preserve displacement through return and re-approach | Measured pose/height, complete per-waypoint and push logs, post-return object truth; a control/candidate development-instance pair |
| 2 | Close a shortfall without undoing progress | Re-observe after each completed action; use signed final net displacement rather than positive pre-retreat accumulation; bounded attempts, cancel and stale-state refusal |
| 3 | Establish a usable push capability | Frozen full independent acceptance on the declared task, contact/trajectory/gripper/attachment evidence; report any gripper false rejection separately without changing its limit |
| 4 | Check repeatability and non-regression | Preregister a small paired development batch only after mechanism works; normal task, recovery/budget and cancellation regressions; preserve failures |
| 5 | Freeze then test unused instances | No tuning on held-out results; old exposed seeds stay exposed. Unseen success cannot be inferred from development results |
| 6 | Test learning and transfer | One genuine failure→proposal→implementation→build→execution→independent verification→accept/reject chain, then reviewed experience and a preregistered retrieval control |

This Coding Agent's engineering repair is **not** evidence that the Runtime Agent
autonomously developed a new skill. The decisive autonomous-development experiment
needs its own frozen initial capability and input boundaries.

P0 integrity and resource checks stay mandatory, but auxiliary architecture,
LIBERO, new dashboards and broad literature work do not consume this turn's main
simulation budget. A stale baseline pin is reported, not silently refreshed.

## Current main-line work — owned here

The retained WorldState trace shows reverse movement during a **successful**
retreat and during the next approach. The frozen push contract samples displacement
before retreat; its result is not a post-return net measurement.

Develop an **opt-in adapter** around the existing motion interface:

1. Obtain a fresh composed world→EE measurement; refuse missing/stale poses.
2. Lift at the measured current xy to a declared transit height.
3. Confirm measured clearance before sending a lateral transit.
4. Transit above the object, confirm clearance again, then lower to the unchanged
   approach/retreat target supplied by the frozen contract.
5. Stop on waypoint failure or cancellation; retain requested and measured poses.
6. Record object state before and after repositioning to expose losses excluded
   from the legacy result interval.

Derive tool clearance from the pinned collision meshes, joint limits and the
declared object top, with an explicit geometric margin and the existing tracking
tolerance. This bounds the tool assembly; it does not prove whole-arm or
continuous-trajectory collision clearance. The Gazebo experiment must test it.

The feature defaults off. No edits to `contracts/push.py`, nine frozen files,
TaskSpecs, success thresholds, gripper gate or shared installed packages.
Runtime promotion, PR/main merge and hardware remain outside this turn.

## This turn's bounded execution

- Unit/interface checks: geometry/coordinate directions, lift failure, insufficient
  measured clearance, stale state, canceled motion and no lateral dispatch after
  an unconfirmed lift. Existing push behavior must remain unchanged when disabled.
- One fresh control and one candidate, both dev seed2000, contact height 0.0200 m,
  target 0.0900 m, at most two pushes; sequential Gazebo, same image/world/validator.
- Before interpreting capability, distinguish physical movement, final state,
  evidence completeness, full acceptance, known false rejection and False Success.
- If the candidate fails, preserve it and identify the failed waypoint/phase before
  changing anything. No repeated identical runs to find a favorable result.
- Only a candidate that clears the mechanism gate earns a paired repeatability
  batch and old-task regression. This first pair cannot estimate a success rate.

## Low-difficulty work distributed to issues

| Issue | Work package | Priority / budget | Independence |
| --- | --- | --- | --- |
| [#231](https://github.com/Yenefa/flexcell/issues/231) | Run-scoped logging and explicit missing-log checks | P1 / 1–2 h | Offline configuration/filesystem checks; no motion or threshold changes |
| [#232](https://github.com/Yenefa/flexcell/issues/232) | Read-only comparison of reported progress and signed final net motion | P1 / 1–2 h | Archived inputs only; no policy or evaluator changes |
| [#233](https://github.com/Yenefa/flexcell/issues/233) | Reusable phase/pose timeline with duplicate and timing checks | P2 / 2–3 h | CSV/JSON diagnostics, no new simulator or acceptance claims |
| [#234](https://github.com/Yenefa/flexcell/issues/234) | Brief current-state/evidence navigation | P2 / 1 h | Preserve historical retractions; no new capability judgment |

All four are open for Junior claim; no individual was assigned without a named
owner. Detailed issue drafts containing internal diagnostics were rejected by
automatic approval review; published issues contain generic scope and acceptance
conditions. Detailed context remains in this local plan and evidence archives.

The main line will explicitly retain Push logs in its own probe runner while
#231 generalizes the fix across entrypoints. That local experiment repair does not
close #231. Existing broader D3/CI/documentation issues are not reclassified or closed.

## Checkpoint

Planning and issue creation: DONE. Candidate implementation and measured outcome
are recorded in `setup/acceptance/evobot_safe_reposition_20261112/` as they occur.
Robot capability is not promoted by completion of this plan or the Junior tasks.

Update: the opt-in adapter is implemented and passed one complete development
instance (9/9 frozen gates); control net −63.655 mm, candidate net +110.145 mm.
Its two returns stay inside the preregistered backslide bound. This is a single
mechanism demonstration, not a repeatability result. Both individual push requests
still fail their narrower contracts, including a second-stroke overshoot.

The ordinary-task regression and an original-source control both reproduce the
documented gripper release stall. Regression remains NOT CLEARED and prevents
formal promotion. T08 isolated state/finishing development may continue; frozen
release changes must follow their existing separate proposal/approval boundary.
No hold-out run or claim of Runtime-autonomous skill development was made.

## Checkpoint — measured feedback and fixed repetition batch

The three-waypoint adapter's first success did not reproduce in the next pilot:
final net −86.016 mm, with roughly 99 mm reverse motion during a retreat LOWER
interval. Preserve that failure. The current isolated v2 adds an optional high
return hold, fresh post-return net-state feedback, 30 mm requests/5 mm overdrive/
one increment and geometry-based stopping, with a maximum of three attempts.
The old low retreat point is honestly reported unreached; no core push edit.

Preregistered A1 B1 B2 A2 A3 B3 completed: previous recovery **0/3**, combined v2
**3/3** full nine-gate task passes, with candidate net **61.558 / 50.537 / 76.131 mm**.
This is repetition on exposed seed2000, not an unseen-instance or statistical
superiority claim. All five candidate primitive strokes still fail their narrower
requested-distance contracts. The precise-stroke limitation remains open.

This turn's ordinary PICK→PLACE→VERIFY regression is PASS with the candidate
overlay; zero identity mismatches and no model calls. The previous two release
failures remain retained and unresolved by this one pass. Broader non-regression
and formal promotion are not cleared. Both motion flags default false.

Source: `setup/acceptance/evobot_push_feedback_20261112/README.md`, complete raw
archive and deterministic analysis scripts. Nine frozen files, push core and
release-related sources are unchanged. Next gates: release consistency, a frozen
unused-instance test, then experience transfer. #231–#234 remain open for their
generalized offline deliverables; local experiment-specific scripts do not close
those work packages. Goal remains active; formal T08/L4 status is unchanged.
