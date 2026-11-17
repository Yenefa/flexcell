# Agentic Flexible Robotic Workcell

**Official name:** Agentic Flexible Robotic Workcell · **repository handle:** `flexcell`

A ROS 2 Jazzy workcell around a ROBOTIS **OpenMANIPULATOR-X**, simulated in Gazebo
Harmonic and planned/executed through MoveIt 2 — built so that an **agent** can
drive it, and so that what the agent did can be checked afterwards by someone who
does not trust it.

> **Positioning: self-evolving agentic robotics.** The research object is how an
> agent develops, operates, validates and keeps improving a robot. FlexCell is the
> execution platform; ROS 2 / Gazebo / MoveIt 2 are means, not the subject.
> Capability ladder **L1 develop → L2 operate → L3 evolve**; division of labour
> **agent decides WHAT, executor decides HOW, independent verification decides
> WHETHER**. See [docs/SELF_EVOLVING_AGENTIC_ROBOTICS.md](docs/SELF_EVOLVING_AGENTIC_ROBOTICS.md)
> and [docs/ORIGIN.md](docs/ORIGIN.md).

## What "agentic" means here

An agent invokes robot capabilities as **skills** — discrete, callable actions such
as "plan and execute to this joint state". The agent decides *what*; the workcell
guarantees *how* it is executed safely.

    agent  ->  skill layer  ->  MoveIt 2  ->  ros2_control  ->  Gazebo / real arm

The skill layer is ours and not vendor-specific. It does not depend on NVIDIA's
Isaac ROS Agent Skills, which live in the *development* plane rather than the
runtime plane — see [docs/SKILL_ARCHITECTURE.md](docs/SKILL_ARCHITECTURE.md).

## Three planes, and the boundaries between them

| Plane | Question it answers | Lives in |
| --- | --- | --- |
| Development skills | how the agent writes and fixes robot code | `development_skills/`, agent tooling |
| Execution skills | what the runtime can be asked to do | `src/flexcell/flexcell_skills` |
| Physical capability | what the arm and gripper can actually achieve | `src/flexcell/flexcell_capabilities`, `experiments/physical_capabilities` |

The boundaries are machine-checked, not documentary:
`scripts/check_skill_boundaries.py` against `config/skill_boundaries.json`
(execution must not depend on development code; runtime may use execution
interfaces only; the physical core must not import execution internals). It fails
the build on a violation rather than warning.

First-party packages:

| Package | Role |
| --- | --- |
| `flexcell_interfaces` | messages, actions, shared types |
| `flexcell_skills` | execution skills: observe / pick / place / verify, task FSM |
| `flexcell_capabilities` | physical capability layer |
| `flexcell_mtc` | MoveIt Task Constructor integration |
| `flexcell_gazebo` | simulation bring-up |

Architecture of record: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) ·
module and evidence boundaries: [docs/REPOSITORY_MODULES.md](docs/REPOSITORY_MODULES.md) ·
branch/version conventions: [docs/VERSION_CONTROL.md](docs/VERSION_CONTROL.md).

## Current work (v0.2): does the agent's access to feedback change what it repairs?

The active research line is a controlled experiment on repair behaviour, kept in
`benchmark/repair_eval` (the judging side) and
`experiments/repair_eval_v02` (the running side).

- **Four conditions** — A no feedback, B real execution feedback, C another run's
  feedback, D real feedback plus bounded guidance. What each condition may read is
  a policy, not a convention: `benchmark/repair_eval/visibility.py` refuses any
  access the policy does not grant, including through symlinks or a path the caller
  mislabels.
- **The task is fixed outside the candidate**: `contracts/` freezes the goal, the
  object set, the tolerances and the allowed edit surface, then judges the repair
  against them — a repair cannot pass by moving the goal.
- **Evidence discipline**: per-file digests, sealed gates, frozen candidates,
  registered seeds and donors, no pooling across source/model/protocol identity,
  and `UNKNOWN` never collapses into pass. Excluded or invalidated batches stay on
  disk and are labelled as such.

Current results, stated with their limits:

| Item | State |
| --- | --- |
| Registered batch (24 slots) | 7 dispatched, then **stopped by protocol** (unconfirmed action terminal); 17 `NOT_RUN` |
| Held-out evaluation | 6 candidate + 6 reference slots executed, `checks_passed: true` |
| Physical admission | `NOT_VERIFIED_PHYSICALLY` |
| Independent judge (G3) | `NOT_RUN` |

Read [experiments/repair_eval_v02/DELIVERY.md](experiments/repair_eval_v02/DELIVERY.md)
before quoting any number: it carries the verification commands and the list of
what the data cannot support.

## Quick start

Prerequisites: Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic, MoveIt 2. Scripts are
numbered by stage:

```bash
scripts/01_provision.sh        # host packages
scripts/02_ros_jazzy.sh        # ROS 2 Jazzy
scripts/03_build_omx.sh        # OpenMANIPULATOR-X from source
scripts/20_launch_gazebo.sh    # simulation
scripts/22_launch_moveit.sh    # planning
scripts/30_plan_execute.py     # one plan-and-execute round trip
```

Do not re-run `03_build_omx.sh` on a machine that already has a working overlay;
it rebuilds the workspace it sits in.

## Verifying a checkout

```bash
# repair-eval suites (417 tests as of 2026-11-17)
python3 -m pytest benchmark/repair_eval experiments/repair_eval_v02 -q

# plane boundaries
python3 scripts/check_skill_boundaries.py

# repository layout — needs a FULL checkout; a sparse one reports missing paths
python3 scripts/check_repository_layout.py

# experiment bookkeeping
python3 experiments/repair_eval_v02/crosscheck_docs.py       # docs and code agree
python3 docs/research/evobot-paper-v02/check_protocol_docs.py
python3 experiments/repair_eval_v02/audit_acceptance.py      # 46/46 criteria covered
python3 experiments/repair_eval_v02/reconcile.py \
  --manifest docs/research/evobot-paper-v02/RUN_MANIFEST.md \
  --records experiments/repair_eval_v02/evidence/v2_matrix_n6.json \
  --registered-only --allow-order-deviation
```

Expected: `status verdict: CONSISTENT`, `order verdict: DEVIATION` for the batch that predates the reordered plan - the deviation is recorded, not hidden.

## Repository map

| Path | What lives there |
| --- | --- |
| `src/flexcell/` | the first-party ROS 2 packages |
| `benchmark/` | evaluators, held-out material, `repair_eval` judging side |
| `experiments/` | running sides: `repair_eval_v02`, `physical_capabilities`, `pilot-001` |
| `docs/` | architecture, ADRs, protocol packages, results |
| `config/` | skill boundaries, version baselines, workcell parameters |
| `scripts/` | setup, launch, gates and audits |
| `runtime/` | planner and model access |
| `evolution/` | self-improvement loop |

## Status

- Milestone of record: **M2 Runtime Decision Foundation** — source implemented,
  qualification incomplete. See [docs/ROADMAP.md](docs/ROADMAP.md).
- The physical arm has **not** been admitted on hardware for this line of work;
  simulation results are not a hardware claim.
- Handoff notes for the next agent: [docs/AGENT_HANDOFF.md](docs/AGENT_HANDOFF.md).

**Maintenance rule:** before coding — which issue, which ADR, which document will
change? After coding — update the issue, record evidence, link the commit. A claim
without an evidence path is a draft, not a result.
