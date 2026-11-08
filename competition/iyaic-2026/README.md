# IYAIC 2026 — competition packaging

**Event:** IYAIC 2026, Henan division, AI & Robotics Innovation (Creative group).
Registration 2026-11-13; division contest 2026-11-21–22.
**Long-term positioning:** Agentic Flexible Robotic Workcell (this repository).

This directory is **competition packaging only**. It does not add a second runtime, does not
refactor the decision / skill / execution / verification boundaries, and does not unfreeze the
n>=50 benchmark freeze. The runtime stays the one in `src/`, `scripts/`, `worlds/`, `infra/`.

## Responsibility split (kept separate on purpose)

| Area | Location | Responsibility |
| --- | --- | --- |
| **Common core** | `src/`, `scripts/`, `worlds/`, `infra/`, `config/` | The single production runtime: skills, decision layer, executor, verifier, simulation plane, data plane. Shared by normal use and by the competition. |
| **Raw evidence** | `setup/acceptance/` (in-repo) and the frozen cloud copy | Immutable measured records referenced by the status index. Never rewritten; historical identity preserved. |
| **Competition showcase** | `competition/iyaic-2026/showcase/` | Demo script, narrative and captured stills/clips for the judges. No runtime logic. |

## Where things are

- Status (implemented / accepted / branch-pending): [DELIVERY_STATUS.md](DELIVERY_STATUS.md).
- Evidence index and identity rules: [evidence/README.md](evidence/README.md).
- Demo narrative and shot list: [showcase/README.md](showcase/README.md).
- Reproduce / run: [REPRODUCE.md](../../REPRODUCE.md), [docs/ROS_MCP.md](../../docs/ROS_MCP.md).

## Hard constraints (from issue #30)

- Do not refactor decision / skill / execution / verification boundaries for the competition.
- Do not auto-unfreeze n>=50.
- Any runtime source/config integration is re-accepted with a **new fingerprint**; old sealed
  evidence, the paused collector and receipts keep their original identity.
- Merging runtime fixes is never validated by cloud unit tests alone where ROS/Gazebo acceptance
  is required.
