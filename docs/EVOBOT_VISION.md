# EvoBot — Project Vision

**Status:** vision document + naming migration plan. No claim of achieved capability.

## 1. What changes

FlexCell asked: *can an agent repair a robot software defect we injected?*
That is a software-engineering stress test. It is kept, but demoted to a side track.

EvoBot asks: *given a robot task it has never done, can an agent acquire the ability
to do it — by executing, failing, diagnosing, improving, and re-verifying?*

These are not the same question at the same difficulty. The second one requires the
agent to decide **what to do**, not just **where the bug is**.

## 2. What EvoBot must not do

- Must not be given the skill order, the source file, the algorithm, or the fix.
- Must not be judged by its own claim of success.
- Must not earn capability by adding pre-written answers per task.
- Must not be scored on a fixed test set it can memorise.

## 3. The loop

```
Task (natural language, no solution)
   -> Observe (scene, robot, history)
   -> Plan (decompose, choose skills, order, budget)
   -> Execute (real Gazebo, structured skills, timeout/cancel/recovery)
   -> Verify (INDEPENDENT evaluator, not the agent)
   -> Diagnose (perception / planning / kinematics / control / grasp /
               state / tooling / runtime / model / environment)
   -> Improve (plan, params, skill code, tool interface, runtime)
   -> Re-execute + regression
   -> Learn (machine-readable experience with evidence and limits)
```

## 4. Capability ladder (the only honest progress metric)

| Level | Name | Meaning |
| --- | --- | --- |
| 1 | Execute | do a known task |
| 2 | Compose | combine known skills into an unseen flow |
| 3 | Recover | diagnose and recover from a real failure |
| 4 | Develop | build a skill that did not exist |
| 5 | Improve | change a skill and pass independent regression |
| 6 | Learn | record, validate, store, retrieve experience |
| 7 | Transfer | reuse experience on an unseen task |
| 8 | Generalise | face a new task type and acquire what it needs |

**Current position: Level 1 is not yet claimed.** Nothing in this repository has
yet run a task issued by the EvoBot benchmark under the EvoBot evaluator. What
exists today is the measuring apparatus, which is a prerequisite, not a result.

## 5. Evidence discipline

Every capability is reported at one of these stages, never collapsed:

| Stage | Test |
| --- | --- |
| Designed | a written spec exists |
| Implemented | code exists and runs |
| Unit Tested | offline tests pass |
| Simulation Tested | ran in Gazebo |
| Independently Verified | the independent evaluator passed it |
| Generalization Tested | passed on held-out instances |

`code exists` is not `capability proven`.

## 6. Naming migration (planned, not executed)

The repository is still named FlexCell and its history is preserved intact. The
migration is deliberately slow because experiment records reference paths:

| Phase | Action | Gate |
| --- | --- | --- |
| 0 (now) | "EvoBot" used as the research programme name in new docs; existing paths untouched | — |
| 1 | Add `benchmark/`, `runtime/`, `skills/`, `evolution/` trees alongside the existing layout | done for `benchmark/` |
| 2 | Introduce `EVOBOT_*` naming in new modules only | after P1 tasks run |
| 3 | Rename repository packages | only with human approval, after a full green regression |

**No bulk rename, no history rewrite, no deletion of FlexCell experiment records.**
