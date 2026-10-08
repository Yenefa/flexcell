# Agentic Flexible Robotic Workcell

**Official project name: Agentic Flexible Robotic Workcell**  
Repository handle: `flexcell`

A ROS 2 Jazzy workcell around a ROBOTIS **OpenMANIPULATOR-X**, simulated in
Gazebo Harmonic and planned/executed through MoveIt 2 - built so that an **agent** can drive it.

> **Origin & motivation:** see [docs/ORIGIN.md](docs/ORIGIN.md) - why this project exists,
> and how it relates to NVIDIA's Agent Skills (Development Plane) vs FlexCell (Runtime Plane).

---

## What "agentic" means here

An agent (coding agent or runtime agent) invokes the workcell's capabilities as **skills**:
discrete, callable robot actions such as "plan and execute to this joint state". The agent
decides _what_ to do; the workcell guarantees _how_ it is executed safely.

    agent  ->  skill layer  ->  MoveIt 2  ->  ros2_control  ->  Gazebo / real arm

**This skill layer is ours, and it is not vendor-specific.** In particular it does not depend
on NVIDIA's Isaac ROS Agent Skills - those live in the _development_ plane, a different layer:

|          | NVIDIA Isaac ROS Agent Skills                                         | flexcell skills                              |
| -------- | --------------------------------------------------------------------- | -------------------------------------------- |
| What     | instruction packs letting coding assistants operate Isaac ROS tooling | runtime robot capabilities the agent invokes |
| Layer    | development plane (authoring / tooling)                               | runtime plane (control)                      |
| Requires | Isaac ROS 5.0, CUDA 13.2+, driver 595+, ROS 2 Lyrical                 | ROS 2 Jazzy (this repo)                      |
| Status   | not used yet; planned as a separate sandbox                           | Day 2 work                                   |

See docs/ORIGIN.md for the full framing.

---

## Roadmap

- [x] **Day 1** - Gazebo Harmonic + MoveIt 2 Plan & Execute, verified on-machine
- [x] **Day 2** - MoveToPose ROS 2 Action (typed request -> MoveIt -> Gazebo -> measured result) - see docs/DAY2_MOVETOPOSE.md
- [x] **Week 1** - deterministic skills (observe / pick / place / verify) + FSM
- [ ] **Week 1 (parallel)** - standalone NVIDIA Development Agent sandbox
- [x] **Week 1.5** - Deterministic Demo Hardening (lifecycle CLI, strict health gate, dual-object scenario, bounded recovery + failure injection)
- [ ] **Week 2 (M2)** - Runtime Decision Foundation - ratified design in docs/WEEK2_PREPARATION.md; tracked via issues #2-#12, RFCs #14/#16 - see docs/ROADMAP.md
- [ ] **M3** - Confidence-Gated Hybrid Agent Benchmark - RFC #15
- [ ] **Later** - Isaac ROS / Isaac Sim / VLA, only when a measured bottleneck justifies it; real robot backend; vision integration

> **0 lines of Jev before the deterministic robot baseline works.**

---

## Project management

The repository is the single source of truth — GitHub-native workflow (Issues, Milestones,
Project board), no external PM tools. Every important idea must have a traceable path:
discussion → Issue/ADR → milestone task → implementation → experiment evidence → docs update.

- [docs/ROADMAP.md](docs/ROADMAP.md) — long-term phases & milestones (M1 done / M2 current / M3 future)
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — execution calendar + maintenance policy
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system architecture (current vs target)
- [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) — experiment log with evidence locations
- [docs/ADR/](docs/ADR/) — architecture decision records (ADR-001: simulation manipulation backend)
- [docs/WEEK2_PREPARATION.md](docs/WEEK2_PREPARATION.md) — ratified Week-2 design of record
- [docs/TRANSFER_BENCHMARK.md](docs/TRANSFER_BENCHMARK.md) — transfer engineering-cost design and offline ledger; AC@90 remains NOT_RUN
- Milestones: **M1** Deterministic Workcell Baseline (done) · **M2** Runtime Decision
  Foundation (current; sub-milestones M2.1/M2.2/M2.3) · **M3** Hybrid Agent Benchmark (future)

**Maintenance rule:** before coding — which Issue? which ADR? which docs need updating?
After coding — update the Issue, record evidence in EXPERIMENTS.md, link the commit.

---

## Status

2026-10-08 offline continuation: the local FSM T1/T3/S1 prefix passed (3 logical
tasks, 5 native episodes), with three Hybrid slots still unclaimed while the home
GPU is offline. A separately pinned [Hybrid resume guard](docs/BOUNDED_HYBRID_GUARD.md)
now rejects zero-fast-call results before terminal commit and subsequent dispatch.
New private candidates remain outside Git; independent custody, online Hybrid
acceptance and n≥50 qualification remain pending.

2026-10-07 mainline composition: `/run_composite` now holds the shared arm lease
across a declared 1..8-stage chain, preserving native episodes and fresh boundary
observations. One Hybrid buffer swap and one S1 regression succeeded (4 episodes);
Clef selected all 9 target decisions. 300 skills tests and 42 instrument/audit tests
passed. The first audit failure from exact float comparison is retained with an
explicit serialization correction; no composite was resampled. See
[API and ownership semantics](docs/COMPOSITE_TASKS.md) and
[retained pilot receipts](setup/acceptance/composite_api_20261007/README.md).

2026-10-06 registered T3 buffer-swap pilot: FSM and Hybrid each completed one
three-stage composite and one S1 source regression; 8 native episodes retained.
Clef selected all 9 target-stage model decisions. The common outer chain is fixed,
and its new engineering work is counted separately; this does not establish
autonomous composition planning or a cost advantage. 260 skills tests and 36
instrument tests passed. The school startup probe now uses an explicit 10s deadline
without changing prompt/calibration identity; DERP network stability remains unaccepted.
See [T3 evidence](setup/acceptance/transferbench_t3_20261006/README.md) and
[startup probe correction](setup/acceptance/startup_health_20261006/README.md).

2026-10-06 transfer-cost instrument: the L1 Skill / L2 composition / L3 engineering-cost
design and an offline append-only ledger are implemented, with 30 targeted tests passing.
The registered T1 simulation pilot completed two target layouts and one source regression
per arm: FSM 2/2 + 1/1, Hybrid 2/2 + 1/1. No task source adaptation was needed by either arm.
The original scorer's string-outcome error is retained and corrected in a separate v2 report;
no episodes were replaced. AC@90 and n≥50 remain frozen. TCP probe timeouts remain unresolved.
See the [T1 pilot receipt](setup/acceptance/transferbench_t1_20261006/README.md).
See [design, official-source corrections and usage](docs/TRANSFER_BENCHMARK.md).
The school's earlier clef routing and controller/time/DDS evidence is preserved in
[its separate acceptance receipt](setup/acceptance/place_transport_20261006/README.md).

2026-10-02 mainline hardening (E-016): lifecycle paths and typed controller
readiness are fixed; Observe now reads confirmed carry authority instead of a
stale topic cache. Cold FSM dual-object S1 passed, and a real stale-A injection
confirmed that the stale cache was not used. Local Jev calibration and frozen
model offline replay
now have measured results; the fast route is ineligible and model replay failed.
Hybrid online smoke still failed, including official API timeouts. The final
fleet is FSM/IDLE, with reset and strict health passing; historical reset/flood
roots remain open. Local commits only, no push. See
[implementation, results and remaining blockers](docs/HARDENING_20261002.md).

2026-10-01 carry implementation update (E-015): the mainline now uses a bounded
Gazebo pose/velocity constraint, confirms engage before lifting, and checks
PLACE's release dependency before admitting deployment. The final single-object
closed loop passed with 2.86 mm error. Earlier S1 smoke batches were 4/5 and 1/2
under different fingerprints; both failures and limitations remain recorded.
This is a new magnetic carry implementation, not an accepted statistical baseline.
See [implementation and online evidence](docs/CARRY_VELOCITY_20261001.md).

2026-10-01 mechanism investigation: reproduced a Fast DDS discovery failure
caused by incomplete fragmented localhost UDP delivery; a 1400-byte transport
limit passed two repetitions. Isolated Gazebo controls support preserved
velocity under pose-only servo as a cause of lift loss. The current fleet and
physics baseline remain unchanged. See [causal evidence and limits](docs/MECHANISM_20261001.md).

2026-10-01 mainline update: both task actions share the policy executor and
episode recorder. The fleet now uses the official `deepseek-flash` endpoint,
with a persistent RMB 5 request budget. One single-object task completed with
8.95 mm measured placement error; a separate S1 smoke batch completed all five
tasks with three successes and two failures. Placement waits for carry-release
acknowledgment, and accepted action results can be read again without resending
the physical goal. S3 recovered a B-only injected failure, and S4 recorded its
expected PLACE failure through the single-object policy seam (one run each).
Protocol v1 E-011 is archived; v2 batches stay separate and
the large batch remains frozen. MTC is pending. See
[current implementation, evidence and limits](docs/DEEPSEEK_20261001.md).

Current: **Week-1.5 accepted; M2 Runtime Decision Foundation is the active milestone** —
see [docs/ROADMAP.md](docs/ROADMAP.md). The table below is the Day-1 verification record.

### Evidence quality (M2.3 audit, 2026-09-28)

A full audit (code + evidence chain + external tech scan) found the
architecture sound but the historical "all green" claims overstated: the
real steady state was "retried to green" (first-attempt success ~30-50% on
several batteries), some parity artifacts read FAIL on disk, and the
batteries could not red-flag anything. The remediation commit (P0-1..3
runtime fixes, hard gates in the batteries, independent referee, measured
parity) addresses the causes; until episode recording lands (#7), treat
every pre-audit acceptance claim in HANDOFF / acceptance/ as **unverified
unless re-run under the gated batteries**. See docs/P2_DECISION_MEMO.md for
the open route decisions.

| Item                                     | State                       |
| ---------------------------------------- | --------------------------- |
| Ubuntu 24.04 + ROS 2 Jazzy               | OK                          |
| Gazebo Harmonic 8.15.0                   | OK                          |
| OpenMANIPULATOR-X (ROBOTIS jazzy source) | OK, 6 colcon packages       |
| Gazebo model + 3 controllers active      | OK                          |
| MoveIt 2 Plan                            | OK, error_code = 1          |
| MoveIt 2 Execute                         | OK, error_code = 1          |
| Real motion in Gazebo physics            | OK, verified via link poses |
| /joint_states consistent with plan       | OK                          |

See DAY1_REPORT.md for the full environment, every problem hit, and the fixes.

## Layout

    agentic_workcell_ws/
    |- README.md
    |- DAY1_REPORT.md          # Day 1 report
    |- docs/ORIGIN.md          # origin & motivation (living document)
    |- docs/DAY2_MOVETOPOSE.md  # Day 2 contract, verification, known blocker
    |- plan_execute.py         # MoveIt Plan & Execute driver
    |- agentic_workcell.repos  # upstream repos (vcstool)
    |- scripts/                # provisioning + launch scripts
    |- src/flexcell/           # OUR packages (tracked)
    |- src/                    # upstream clones (ignored, via .repos)

## Reproduce

    mkdir -p ~/agentic_workcell_ws/src && cd ~/agentic_workcell_ws
    vcs import src < agentic_workcell.repos
    source /opt/ros/jazzy/setup.bash
    rosdep install --from-paths src --ignore-src -r -y
    colcon build --symlink-install \
      --packages-up-to open_manipulator_bringup open_manipulator_moveit_config

## Run

    # Terminal 1 - Gazebo
    ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py

    # Terminal 2 - MoveIt 2 + RViz
    ros2 launch open_manipulator_moveit_config open_manipulator_x_moveit.launch.py use_sim:=true

    # Terminal 3 - Plan & Execute (optional joint target)
    python3 plan_execute.py 0.6 -0.9 0.9 0.5

## Known limitations

- WSL exposes no /dev/dri and the WSL dxg graphics path currently fails
  (dxgkio_query_adapter_info: Ioctl failed: -22), so Gazebo/RViz render on CPU
  (llvmpipe). Simulation is unaffected; only the GUI is slow.
- CUDA toolkit is intentionally NOT installed - nothing in Day 1 needs it.
- Isaac ROS 5.0 requires CUDA 13.2+ / driver 595+ / ROS 2 Lyrical, so it cannot share this
  Jazzy environment. It belongs in a separate Docker-isolated sandbox, not in this workspace.
