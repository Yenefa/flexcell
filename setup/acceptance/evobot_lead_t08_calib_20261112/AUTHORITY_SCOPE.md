# T08 Recovery — BOUNDED AUTONOMOUS DEVELOPMENT authority (recorded 2026-11-12)

**Source**: direct human directive. Base commit: the live HEAD when work started (**`07f86559`**, not the
`c0261702` named in the directive — that commit was already superseded by my own retraction).

---

## 1. What I MAY change without asking again

| scope | covers |
| --- | --- |
| `contracts/push_recover.py` | the recovery logic itself — how a shortfall becomes a next request |
| recovery execution / scheduling code | `run_push_recovery.py`, recovery drivers |
| **interfaces required for safe re-positioning** | anything I must call to put the arm back on a legal contact side |
| unit / integration tests, run scripts, **diagnostic tools** | including new instrumentation |
| isolated ROS 2 build + Gazebo verification | overlay workspace, candidate runs |

**I may iterate autonomously**: OBSERVE → HYPOTHESIZE → PATCH → TEST → MEASURE → ACCEPT/REJECT → NEXT.
If the first fix fails I continue **without** returning for approval, as long as it stays inside the above.

## 2. What I may NOT change — hard limits, no exceptions

| frozen | note |
| --- | --- |
| frozen TaskSpec | |
| **30 mm push lower bound** | |
| existing success thresholds | |
| **frozen evaluator** (`evaluate.py`, sealed_evaluate.py, …) | all 9 pinned files |
| acceptance evidence | never deleted, never rewritten |
| held-out isolation rules | |
| **`gripper` gate limit** | known miscalibrated; **I may report the mis-rejection, I may not change the limit** |
| `contracts/push.py` core contract | **not in the granted list.** The retreat/approach geometry lives here; if the fix requires editing it, that is a decision to escalate, not to take |

**Explicitly**: a fix that raises the pass rate is **not** thereby correct. Modification authority is not
validation.

## 3. What still needs human approval

- changing the Mission or the final goal
- changing frozen evaluator / thresholds
- promoting a validated change from the isolated workspace **into the formal execution baseline**
- unauthorised LLM spend, bypassing budget gates
- main merge, PR, release, real hardware, deleting user assets

**This authorisation is for isolated development and verification, NOT for publishing to the baseline.**

## 4. Reporting obligations regardless of outcome

Must be reported **separately**, never conflated:

1. did a physical push occur
2. is the target end state satisfied
3. are trajectory and contact evidence valid
4. does the full independent acceptance pass
5. is a known acceptance false-rejection present
6. is there any False Success

**Fixing recovery ≠ finishing gripper calibration.** They must never be reported as one result.

## 5. Experiment discipline

| stage | content |
| --- | --- |
| A | static diagnosis on existing archives |
| B | pure-function / interface tests (contact side, coordinate direction, state update, cancel) |
| C | single-instance positive and negative cases in isolated sim |
| D | paired original-vs-candidate on same task, seed, validator |
| E | freeze, then unseen instances + regression on old tasks |

**Do not start with dozens of Gazebo runs.** First prove the basic re-positioning happens in real simulation.
Every round must state in advance which hypothesis it separates, the minimum sample, and that the result
can change the next decision. Keep every failure.

## 6. Blocking rule

"Touches sensitive code" does **not** mean all work stops. Order of resolution: is isolated candidate
development permitted → can a pure function reproduce it → do existing logs settle it → can an overlay be
built without touching frozen files → can existing simulation be used → only then escalate.

Output `BLOCKED` with: the exact blocking point, evidence already obtained, the minimum authorisation needed,
the cheapest substitute experiment, and what else can proceed meanwhile.

