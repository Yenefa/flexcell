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
decides *what* to do; the workcell guarantees *how* it is executed safely.

    agent  ->  skill layer  ->  MoveIt 2  ->  ros2_control  ->  Gazebo / real arm

**This skill layer is ours, and it is not vendor-specific.** In particular it does not depend
on NVIDIA's Isaac ROS Agent Skills - those live in the *development* plane, a different layer:

| | NVIDIA Isaac ROS Agent Skills | flexcell skills |
|---|---|---|
| What | instruction packs letting coding assistants operate Isaac ROS tooling | runtime robot capabilities the agent invokes |
| Layer | development plane (authoring / tooling) | runtime plane (control) |
| Requires | Isaac ROS 5.0, CUDA 13.2+, driver 595+, ROS 2 Lyrical | ROS 2 Jazzy (this repo) |
| Status | not used yet; planned as a separate sandbox | Day 2 work |

See docs/ORIGIN.md for the full framing.

---

## Roadmap

- [x] **Day 1** - Gazebo Harmonic + MoveIt 2 Plan & Execute, verified on-machine
- [ ] **Day 2** - expose Plan/Execute as an agent-callable skill interface
- [ ] **Week 1** - deterministic skills (observe / pick / place / verify) + FSM
- [ ] **Week 1 (parallel)** - standalone NVIDIA Development Agent sandbox
- [ ] **Week 2+** - DecisionPolicy abstraction (FSM / Jev / LLM) - see issue #1
- [ ] **Later** - Isaac ROS / Isaac Sim / VLA, only when a measured bottleneck justifies it

---

## Status - Day 1 complete

| Item | State |
|---|---|
| Ubuntu 24.04 + ROS 2 Jazzy | OK |
| Gazebo Harmonic 8.15.0 | OK |
| OpenMANIPULATOR-X (ROBOTIS jazzy source) | OK, 6 colcon packages |
| Gazebo model + 3 controllers active | OK |
| MoveIt 2 Plan | OK, error_code = 1 |
| MoveIt 2 Execute | OK, error_code = 1 |
| Real motion in Gazebo physics | OK, verified via link poses |
| /joint_states consistent with plan | OK |

See DAY1_REPORT.md for the full environment, every problem hit, and the fixes.

## Layout

    agentic_workcell_ws/
    |- README.md
    |- DAY1_REPORT.md          # Day 1 report
    |- docs/ORIGIN.md          # origin & motivation (living document)
    |- plan_execute.py         # MoveIt Plan & Execute driver
    |- agentic_workcell.repos  # upstream repos (vcstool)
    |- scripts/                # provisioning + launch scripts
    |- src/                    # upstream sources (not tracked)

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

