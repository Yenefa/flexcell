# Full-config scheduling: what was measured, what is still a guess

Status: **diagnosis only.** No fix is claimed and no task was accepted. #237 stays open.

## Why this page exists

#237 reports that tasks complete under the task-specific configuration but stall
under the complete default configuration. Before proposing a repair, the two
graphs have to be shown to differ in a way that can produce that symptom. That
comparison is below, with the runtime observations that produced it.

## What was run

```bash
source /opt/ros/jazzy/setup.bash
source install/setup.bash
source ~/agentic_workcell_ws/install/setup.bash      # vendor bringup, outside this repo
ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py gui:=false
```

Observed 35 s after launch (Ubuntu 24.04 / ROS 2 Jazzy / gz vendor build, headless):

| measurement | value |
| --- | --- |
| nodes | **7**: /arm_controller, /controller_manager, /gripper_controller, /gz_ros_control, /joint_state_broadcaster, /robot_state_publisher, /ros_gz_bridge |
| topics | 22 |
| actions | 2: /arm_controller/follow_joint_trajectory, /gripper_controller/gripper_cmd |
| controllers | arm_controller **active**, gripper_controller **active**, joint_state_broadcaster **active** |
| /clock | 200.012 Hz (min 4 ms, max 6 ms) |
| gz process | `gz sim empty_world.sdf -v 1 -r -s` |
| warning | `OpenManipulatorXSystem: Executor is not available during hardware component initialization ... Skipping node creation!` |

## The two graphs, compared

The task-specific graph is the repository's own `flexcell_skills/launch/trusted_sim.launch.py`
(used by `scripts/sim_smoke.py` and `scripts/sim_window.py`). The complete graph is the
vendor bringup launched by `scripts/20_launch_gazebo.sh`.

| aspect | complete config (vendor launch) | task config (repo launch) |
| --- | --- | --- |
| world | `empty_world.sdf` (vendor default) | a **declared** flexcell world under `worlds/`, sha256 checked against the task declaration |
| skill layer | **none** - no task_fsm / pick / place / carry / observe / verify server | `move_to_pose.launch.py` + `week1.launch.py` with a declared `params_file` (+ `flexcell_mtc` when skill_backend=mtc or carry=detachable_joint) |
| physics trace | not bridged | `/flexcell/physics_trace` bridge is part of the graph |
| camera | not bridged | `/flexcell/camera/rgb` + camera_info bridged, `--headless-rendering` |
| startup ordering | independent spawners; nothing gates the model spawn | event-chain: spawn -> joint_state_broadcaster -> controllers, and any upstream failure **shuts the graph down** instead of continuing |
| move_group | separate script (`22_launch_moveit.sh`) | included in the same launch, `start_rviz:=false` |
| robot description | from the vendor package | in-memory xacro string passed to `ros_gz_sim create -string` |

## What is established

1. **The complete config is not the same graph as the task config**, and by a wide
   margin: it never loads the task world and it contains none of the six skill
   servers. "Run the task under the complete config" therefore does not exercise
   the same software, so a stall there cannot be attributed to the task alone.
2. **The hardware component does not initialize in the complete config**: the
   controller manager logs `Executor is not available ... Skipping node creation!`
   for `OpenManipulatorXSystem`. The controllers still report `active`, so this is
   a silent degrade rather than a startup failure - the graph looks healthy while
   one hardware component was skipped.
3. The physics clock itself is healthy (200 Hz, tight bounds), so the stall #237
   describes is not "the simulator did not step".

## What is still a guess

- That the skipped hardware component is *the* cause of the scheduling interruption.
  It is the strongest candidate in the evidence above, but nothing here connects it
  to a failed task attempt; that requires dispatching a task on this graph and
  watching where it stops.
- That the missing `PhysicsTrace` bridge is what makes the observation layer go
  quiet. Plausible (there is no such topic in the complete graph) but unproven.
- That startup ordering (spawners not gated) contributes. The task graph gates it
  explicitly, which suggests the authors saw a race, but no log in this attempt
  shows one.

## Isolation experiments needed (each needs the simulator, ~10 min)

1. Start the complete config, dispatch one T08 push with `scripts/sim_smoke.py`
   against the same world, and record which node stops publishing first.
2. Re-run with the vendor hardware component warning silenced by providing an
   executor, and compare whether the dispatch still stalls.
3. Re-run the complete config with the `/flexcell/physics_trace` bridge added and
   check whether the observation side recovers while the task side still stalls.

Until those run, the correct statement is: **the graphs differ in composition and
one hardware component is skipped; neither has been shown to cause the stall.**

## Reproduce

```bash
# the evidence above
ros2 launch open_manipulator_bringup open_manipulator_x_gazebo.launch.py gui:=false &
sleep 35 && ros2 node list && ros2 control list_controllers && ros2 topic hz /clock
```


## Follow-up experiments (2026-11-16, same WSL host)

Five bounded attempts were made to close the "is it the cause?" gap above. None
produced a task acceptance, and the last three hit an environment gate that this
host cannot satisfy. Recording them so nobody repeats them by accident.

| run | what was tried | result |
| --- | --- | --- |
| E1 | start the repo skill layer (`week1.launch.py` + `move_to_pose.launch.py`) **on top of** the complete vendor launch | all seven servers logged `... server up`; but at that moment `ros2 node list` returned only the six skill nodes, `ros2 action list` was **empty**, and no `/flexcell/*` topic appeared. The `OpenManipulatorXSystem ... Skipping node creation` warning recurred. Whether the vendor nodes had exited or discovery was just late is **unresolved** |
| E2 | control: one bounded task through `scripts/sim_smoke.py` (repo-owned task config) | `HARNESS_ERROR: installed/source identity mismatch`, `physical_tasks_dispatched: 0`. `infra/runtime_identity.py` was called without `FLEXCELL_REPO`/`FLEXCELL_INSTALL` |
| E3 | same control with those variables declared (as in `infra/Dockerfile.sim`) | identity check now ran but reported **46 mismatches / 64 python files**; control still refused |
| E4 | source the vendor underlay *before* this repo's overlay | mismatches dropped to **4**, all `launch/*.launch.py` in `install/share`; `find_spec('flexcell_skills')` resolved into `build/flexcell_skills`, showing a workspace overlay conflict |
| E5 | `colcon build --symlink-install --packages-select flexcell_skills` to refresh the install copies | still 4 launch-file mismatches; build warned that `flexcell_skills` **also exists in `/home/ros/agentic_workcell_ws/install`**. Control still refused |

### What this changes

- **Confirmed again:** the complete config silently skips a hardware component
  while its controllers report `active`, and it is missing the task graph's
  bridges and skill layer. Starting the skill layer on top brings the processes
  up but did not produce an observable action surface in E1.
- **New finding, environment not code:** this host has two installed
  `flexcell_skills` copies (the vendor underlay and this repo's overlay), so
  `runtime_identity.py` cannot pass and `sim_smoke.py` refuses to dispatch any
  task. Therefore **no control task run is possible here**, and no conclusion
  about the scheduling stall can be drawn from E1-E5.
- The old guesses stay guesses. In particular E1's empty action list must not be
  reported as "the complete config breaks actions": it may be discovery timing.

### Where to continue

The control belongs in the declared CI container (`infra/Dockerfile.sim`),
which sets `FLEXCELL_REPO=/opt/flexcell/repo` and
`FLEXCELL_INSTALL=/opt/flexcell/ws/install` and has a single overlay. Run the
three isolation experiments from the previous section there, with the original
failure data preserved. Until then #237 must stay open and unclaimed as fixed.


## Simulation runs completed (2026-11-16, WSL2 / ROS 2 Jazzy)

The identity gate that blocked E2-E5 was an **install-layout mistake on this
host**, not a repository defect: `infra/runtime_identity.py` expects the CI
merge-install layout (`$FLEXCELL_INSTALL/share/flexcell_skills/launch/...`),
while the first local build used colcon's isolated layout
(`install/flexcell_skills/share/...`). Rebuilding with
`colcon build --merge-install --symlink-install --install-base install_merged`
(which is what `infra/Dockerfile.sim` does) made identity report
`mismatches = 0`, and real tasks could then be dispatched.

All runs below are one declared, bounded task each. No replacement attempts,
no model calls, no hardware.

| run | graph / world | backend | outcome |
| --- | --- | --- | --- |
| CONTROL-1 | repo-owned `trusted_sim.launch.py`, declared world `f78a469d…` | `velocity_servo` / legacy | `physical_tasks_dispatched: 1`, `ROBOT_FAILURE`: `PICK_A(attempt=1) ... skill/carry backend configuration mismatch`. Harness completed, `owned_launch_exit: 0`. A typed failure, **not** a harness error |
| CONTROL-2 | repo-owned `trusted_sim.launch.py`, declared world `422f5a6a…` | `teleport` / legacy | **PASS** - `OUTCOME_SUCCEEDED`, `ERR_NONE`, `PICK_A:OK / PLACE_A:OK / VERIFY_A:OK`, `final_position_error_m = 0.0092`, 14.9 s. `qualification: FUNCTIONAL_SMOKE_ONLY`: teleport is a non-physical shortcut, so this is a graph/harness control, **not a physical capability claim** |
| E7 (discarded) | complete config + skill layer | velocity_servo | confounded: leftover skill processes from an earlier run produced duplicate nodes and a "more than one action server for /run_pick_place" warning. Not used for any conclusion |
| E10 (clean) | `open_manipulator_x_gazebo.launch.py` (`empty_world.sdf`) + `week1.launch.py` + `move_to_pose.launch.py`, no duplicate skill nodes | velocity_servo | **`ERR_SKILL_FAILED`: `policy abort (OBSERVE_FAILED): leg-start observe failed ... cause=ERR_WORLD_STATE_UNAVAILABLE`**, 13.5 s. 12 actions were available, so the action surface itself is fine |
| E10-bridge | same graph, `ros_gz_bridge parameter_bridge /flexcell/physics_trace` added | - | topic created, **0 messages** in the observation window (`echo_bytes = 0`). Adding a bridge cannot conjure a producer |
| E10-world | same graph before bridge | - | `/flexcell/physics_trace` absent from `ros2 topic list` (count 0) |

### What is now established

1. **The observation interruption is a missing producer, not a missing ROS
   bridge.** Under the task config the declared world feeds the observation
   layer and a task reaches PICK (CONTROL-1) or completes (CONTROL-2). Under the
   complete config the world is `empty_world.sdf`, no `physics_trace` topic
   exists, and the task is rejected at OBSERVE with
   `ERR_WORLD_STATE_UNAVAILABLE`. Bridging the topic creates it but produces no
   messages. This is a graph-composition difference, reproducible in ~1 minute.
2. **The action surface is not the problem.** With the skill layer started on
   top of the complete config, all 12 actions are listed and a goal is accepted;
   the failure occurs inside the first OBSERVE stage. E1's empty action list was
   a stale-discovery/leftover-process artifact and is withdrawn.
3. **The skipped hardware component does not stop the graph.** It warns on
   every complete-config start, yet 3 controllers are active and `/clock` runs
   at 200 Hz. It is not, by itself, a scheduling failure.

### What is still NOT established

- **No scheduling stall was reproduced.** Every dispatched run terminated in
  13-15 s with a typed result (PASS, ROBOT_FAILURE, or OBSERVE_FAILED); nothing
  hung. The stall #237 describes may belong to the environment disconnection
  the issue itself asks to keep separate ("运行时失联" vs "图内调度停顿") -
  that separation is still required and this host cannot reproduce the former.
- **No physical-backend PASS was obtained.** CONTROL-1 (`velocity_servo`)
  failed at the backend-parameter check; CONTROL-2's PASS used `teleport` and
  is explicitly `FUNCTIONAL_SMOKE_ONLY`. So "the task config completes the
  physical task" is **not** a claim this page makes.

### Reproduce

```bash
colcon build --base-paths src/flexcell --merge-install --symlink-install \
  --install-base install_merged --packages-up-to flexcell_skills
source install_merged/setup.bash
export FLEXCELL_REPO=$PWD FLEXCELL_WS=$PWD FLEXCELL_INSTALL=$PWD/install_merged
python3 scripts/sim_smoke.py --out /tmp/control --backend teleport --skill-backend legacy
```

#237 remains open: the graph-composition cause of the observation break is
measured, the scheduling stall is not reproduced, and no fix has been accepted.
