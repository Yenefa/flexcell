# EvoBot Task Benchmark v0.1

**Status: Designed + Implemented + Unit Tested. Not yet executed on the robot.**

## 1. Design sources (absorbed, not migrated)

| Source | Borrowed | Not borrowed |
| --- | --- | --- |
| LADDER | 8 task categories: single destination, transfer, split destination, relay, revisit, exclusion, ordered, duplicates | its simulator, its robot |
| ManiSkill 3 | physical-operation task types: push, stack, clutter, insertion | its assets, its policies |
| RoboCasa365 | everyday-task composition and sub-task annotation idea | RoboSuite, 10 GB assets |
| BEHAVIOR-1K | "can it finish a task a human needs", not "can it grab a cube" | OmniGibson, mobile manipulation |
| LIBERO | experience transfer across tasks | leaderboard scores as evidence of generalisation |

**Platform stays ROS 2 Jazzy + Gazebo Harmonic + MoveIt 2 + OpenMANIPULATOR-X.**
Licences of the above were not reviewed; no code, model, asset or data was copied,
so no licence obligation is created. Only task *concepts* were used.

## 2. Robot envelope (constraints that decide what is feasible)

4 arm joints + 1 gripper, reach ~380 mm, payload 500 g. Measured scene facts:

- boxes: 35 mm cubes at z = 0.0175, three of them (red / blue / green)
- bins: two, r = 60 mm, at (0.12, -0.15) and (0.25, 0.05)
- workspace limit enforced by the planner: |x|, |y| <= 0.45, z in [-0.15, 0.75]

Tasks outside this envelope are not registered as "hard", they are registered as
**infeasible for the current platform** and not emitted.

## 3. Splits

| Split | Seeds | Instances | Purpose |
| --- | --- | --- | --- |
| train | 1000-1011 | 72 | the agent may execute, learn and modify skills on these |
| val | 2000-2005 | 36 | regression after every improvement |
| held_out | 9000-9005 | 36 | **agent runtime must not read**; measures real generalisation |

Splits use disjoint seed ranges so no instance can appear twice. Instances are
deterministic from `(template, seed)`, so a third party can regenerate any held-out
spec to re-check a claim without the agent ever seeing the answer.

## 4. Isolation requirement — ENFORCED (2026-11-11)

The evaluator reads the spec; the agent must not. Both still live in the same checkout,
but the three answer-bearing trees are now `root:ros 0750/0640` and the agent runs as
uid 1001 with cleared groups, so it is denied by the kernel rather than by convention.

`scripts/heldout_isolation.py apply|verify|restore|stage-public`. Verification is
bidirectional: the agent must be denied **and** the evaluator must still return both a
pass and a fail. `restore` (chmod 755) is the mutation path and makes `verify` exit 1.

`benchmark/generators/` is locked too, and that is the substantive correction: sealing
the answers into `/etc/evobot/sealed` was necessary but insufficient, because a public
held-out task plus a readable generator reconstructs the sealed `expected_goal`. That
attack succeeded in under a second before this change.

Not a kernel namespace. A root process, and WSL interop (uid 1001 invoking a Windows
binary), still read the same bytes; both are measured and reported by the verifier.
Historical v0.1 held-out specs remain in git history with answers in clear text and stay
retired as contaminated.

## 5. TaskSpec v0.1

`benchmark/schemas/taskspec.schema.json`. Required fields: `task_id`,
`template_id`, `random_seed`, `instruction`, `objects`, `zones`, `expected_goal`,
`evaluator_version`, `execution_budget`, `split`.

Two rules the schema encodes because they were violated in earlier work:

1. `objects` declares **every object in the scene**, including ones that must not
   move — otherwise the evaluator has no initial pose and cannot prove they stayed.
2. `instruction` is natural language only. A test asserts it never contains skill
   names, file names, or language that would leak the solution.

## 6. Evaluator v0.1

`benchmark/evaluators/evaluate.py`, pure function of `(spec, final_state)`.

- never reads agent output; `agent_claimed_success` is only used to compute
  **false_success**, which the mission requires to stay at zero
- deterministic: same two inputs give the same verdict, so it can be re-run by a
  third party
- each clause reports its own measured value and threshold
- tolerances are declared constants; changing one requires bumping the version, and a
  test asserts the generator and evaluator versions agree

Declared tolerances: horizontal 20 mm, resting height 20 mm, unmoved 15 mm,
stack tier 30 mm.

## 7. What is verified today

```bash
python3 -m pytest benchmark/tests -q     # 12 passed
```

| Component | Stage reached |
| --- | --- |
| TaskSpec schema | Designed, Implemented, Unit Tested |
| Generator T01-T06 | Designed, Implemented, Unit Tested |
| Generator T07-T10 | **Designed only** — refuse with `NotImplementedError` |
| Evaluator | Designed, Implemented, Unit Tested |
| Instance sets (144) | Implemented, deterministic |
| Agent task execution | **Not started** |
| Gazebo final-state feed into evaluator | **Not started** |
