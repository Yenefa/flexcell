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
