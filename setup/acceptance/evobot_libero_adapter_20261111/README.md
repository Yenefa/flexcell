# EvoBot -> LIBERO adapter: it drives the robot, but does not solve the task

## What was added

The previous round showed an official task loads, steps and grades, with a deliberately idle policy.
This round adds the piece that was missing: a **pose -> Cartesian delta adapter** plus a phase controller
(approach, descend, close, lift, transport, lower, release, retreat), closing the loop on the measured
end-effector every step instead of replaying fixed actions.

## Result, in the official environment with the official predicate

| phase | outcome |
| --- | --- |
| approach | reached, 19 steps, err 0.012 |
| descend | **stopped at eef z = 0.08**, short of the nominal grasp height |
| close / lift / transport / lower / release / settle / retreat | all executed |
| **object final position** | **[-0.119, -0.24, 0.038] - its start pose** |
| **official success** | **False** |

The object never left its start pose, so this is a **grasp failure**, not a placement failure.

## The root cause was separated by experiment

Asked the arm to reach z = 0.02 in **free space**, away from the can and the basket: it reached **0.02**.

So the arm is capable and the limit is not reach - **the can blocked the fingers**. They came down onto the
lid at about z = 0.08 instead of straddling the can body, and closed on nothing.

## Status

| item | status |
| --- | --- |
| pose -> delta adapter | **IMPLEMENTED** |
| phase controller running in the official env | **SIM_TESTED** |
| official task completed by EvoBot | **NOT ACHIEVED** |
| independent re-check | verify.py in this directory |

## Not claimed

- that the LIBERO task is solved;
- that a 0% success rate here says anything about capability - **the grasp pose does not line up**;
- **perception is ORACLE** (simulator state, not a camera), so any result is an **execution** result, not a perception result;
- that this policy transfers to another task (not tested).

## Next step, concrete

The only blocker is grasp alignment: close the fingers around the can body (about z 0.06-0.09) rather than
on its lid, and tighten the x/y alignment to under 5 mm before descending. That is a pose-tuning problem,
not an architecture problem.
