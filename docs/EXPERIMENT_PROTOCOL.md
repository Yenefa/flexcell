# EvoBot Experiment Protocol

Rules that exist because breaking them produces numbers nobody can use.

## 1. Three arms, same task, same gate

| Arm | May plan | May edit skills | Purpose |
| --- | --- | --- | --- |
| A — Deterministic | no (mechanical plan from spec) | no | measure the stack |
| B — Runtime agent | yes | no | measure planning + recovery |
| C — Self-evolving | yes | yes | measure self-improvement |

All three use the **same spec, same seed, same evaluator, same tolerances**. A
difference between arms is attributable only if everything except the arm is held
fixed.

**Resource honesty:** if arm C gets more tokens or wall-clock than arm A, that must
be reported alongside the result. An advantage that exists only because C had a
bigger budget is a budget result, not a capability result.

## 2. Pre-registration

Before a run that could change a conclusion, write down:

1. the falsifiable proposition;
2. what outcome would refute it;
3. what happens on failure (usually: revert).

This is not ceremony. In the FlexCell track, the run that finally located a root
cause was the one where the rollback rule was written first — the earlier three
attempts guessed and left debris.

## 3. Grading is never done by the arm under test

The evaluator reads `(spec, observation)`. It never reads the agent's claim, its
log, or its reasoning. `agent_claimed_success` is used for exactly one purpose:
computing `false_success`, which must stay at zero.

## 4. Observation must be measured, not assumed

An object with no measured pose is recorded as **absent**, never as "unchanged".
`not observed` is not `did not move`. The bridge enforces this.

## 5. Failure must be attributed before it is fixed

Mandatory classes: perception / planning / kinematics / control / grasp / state /
tooling / runtime / model / environment. If the evidence does not support a class,
write **UNKNOWN**.

The expensive lesson from the previous track: three published root causes were
wrong, and every one of them was a plausible story told before the data was read.
**Instrument first, then explain.**

## 6. Nothing is deleted

Failed runs stay. Retracted conclusions stay, marked retracted. A record that only
contains successes cannot be audited.

## 7. Every capability claim names its rung

Designed → Implemented → Unit Tested → Simulation Tested → Independently Verified →
Generalization Tested. "Code exists" is not a rung.

## 8. Splits are disjoint and held-out is sealed

train seeds 1000-1011, val 2000-2005, held_out 9000-9005. The agent may execute
train and val. It must not read held_out. **Today that seal is specified but not
enforced** — until it is, no held-out result may be reported.

## 9. Small samples are labelled as such

n=1 is exploration. Report n, the failure distribution, and no confidence interval
on a single run.
