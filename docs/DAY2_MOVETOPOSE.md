# Day 2 - MoveToPose ROS 2 Action

Replaces `Human -> RViz -> Plan -> Execute` with:

    typed request -> MoveToPose Action -> MoveIt 2 -> Gazebo
                  -> actual state check -> typed result

Everything below the Task Policy works correctly **without an LLM**.

## Packages

    src/flexcell/flexcell_interfaces   action/MoveToPose.action
    src/flexcell/flexcell_skills       flexcell_skills/move_to_pose_server.py
                                       config/move_to_pose.yaml
                                       launch/move_to_pose.launch.py
                                       test/ee_probe.py
                                       test/move_to_pose_client.py
                                       test/direct_execute_cancel_test.py

The Skill Server is deliberately thin: validation, admission, single-arm mutual
exclusion, cancellation, MoveIt request lifecycle, result normalization,
structured logging. No Runtime Agent, no Jev, no benchmarks, no pick/place.

## Interface

### Goal

    string   request_id              # server generates one when empty
    PoseStamped target               # frame_id must resolve via TF
    string   motion_profile_id       # server-side whitelist key
    uint64   expected_world_revision # 0 = gate disabled (Day 2 fixed-scene mode)
    uint32   deadline_ms             # 0 = default; server clamps to a hard cap

### Feedback

    uint8 phase       VALIDATING | PLANNING | EXECUTING | CHECKING | STOPPING
    uint32 elapsed_ms

### Result

    uint8  outcome       SUCCEEDED | FAILED | CANCELED | STATE_UNKNOWN
    uint16 error_code    see taxonomy below
    int32  moveit_error_code        # raw MoveItErrorCodes.val, preserved
    PoseStamped reached_pose
    bool   has_reached_pose         # measured from real TF, not MoveIt's belief
    float64 position_error_m
    float64 orientation_error_rad
    bool   orientation_enforced     # false => position-only solver, stated not silent
    uint64 world_revision_before
    uint64 world_revision_after     # 0 = unavailable in Day 2 fixed-scene mode
    bool   execution_started
    int32  controller_error_code    # FollowJointTrajectory code (controller_action backend)
    bool   preempted                # a running trajectory was measurably cut short
    bool   stop_confirmed           # strict stop confirmation (see Stop semantics)
    string evidence_id              # key into the JSONL log
    string detail

### Error taxonomy

    request / state   INVALID_GOAL | FRAME_UNAVAILABLE | STALE_WORLD | RESOURCE_BUSY
    planning          IK_UNREACHABLE | NO_COLLISION_FREE_PLAN | PLANNING_TIMEOUT
    execution         CONTROLLER_REJECTED | EXECUTION_FAILED | EXECUTION_TIMEOUT
    result            POSE_NOT_REACHED | STATE_UNAVAILABLE | CANCELED | STATE_UNKNOWN

`STATE_UNKNOWN` latches motion off until the state is reconfirmed.

## Behaviour decisions

- **Success is measured, not inherited.** MoveIt reporting execution success is
  NOT enough. `SUCCEEDED` requires planning + execution + a measured end-effector
  pose (from TF) inside the configured tolerance.
- **IK is pre-checked** against `/compute_ik` before planning, so an unreachable
  target returns `IK_UNREACHABLE` in ~1 s instead of burning the OMPL budget and
  reporting a timeout.
- **Orientation is not enforced** because the shipped OpenMANIPULATOR-X KDL config
  sets `position_only_ik: true`. This is reported explicitly via
  `orientation_enforced=false`; it is never a silent relaxation.
- **The IK constraint sphere is tighter than the success tolerance**
  (`planning_constraint_radius_m: 0.008` vs `position_tolerance_m: 0.02`) so the
  achieved pose lands comfortably inside tolerance rather than on its boundary.
- **Execution dispatch is selectable.** Default `controller_action` (FlexCell owns the
  controller goal, so cancel is real). `moveit_execute_trajectory` is kept for audit
  but is not cancellable - see the investigation below.
- **Callers never supply raw velocity/acceleration.** Only a whitelisted
  `motion_profile_id` is accepted.
- **`expected_world_revision != 0` is refused** while the revision gate is disabled
  rather than faked.

## Verification (all executed on-machine)

| # | Case | Result |
|---|------|--------|
| 1 | Happy path A | `SUCCEEDED`, pos err 0.0060 m, phases VALIDATING/PLANNING/EXECUTING/CHECKING |
| 2 | Happy path B (different target) | `SUCCEEDED`, pos err 0.0057 m |
| 3 | Unreachable target | `IK_UNREACHABLE` ("NO_IK_SOLUTION for link end_effector_link"), `execution_started=false` |
| 4 | Target outside workspace | `INVALID_GOAL` |
| 5 | Non-normalized quaternion | `INVALID_GOAL` |
| 6 | Motion profile not whitelisted | `INVALID_GOAL` |
| 7 | `expected_world_revision=7` with gate off | `STALE_WORLD` |
| 8 | Timeout (deadline 800 ms on a 3.7 s motion) | `EXECUTION_TIMEOUT`, STOPPING phase, stop confirmed |
| 9 | Cancel | `CANCELED` + `stop_mode` reported honestly (see blocker) |
| 10 | Day 1 regression | `plan_execute.py`: PLAN/EXECUTE `error_code=1`, MOTION_DETECTED |

## Cancellation / Preemption Investigation

### Original problem

`/execute_trajectory` accepted a cancel request but the trajectory still ran to completion:

    cancel response:   goals_canceling: 0
    execute result:    SUCCESS
    robot:             reached the planned endpoint (deviation 0.00000 rad)

FlexCell could therefore not honestly claim "a running trajectory can be reliably
interrupted".

### Execution chain (measured from the live ROS graph, not assumed)

    FlexCell MoveToPose server        /move_to_pose_server
      -> /execute_trajectory                              [moveit_msgs/ExecuteTrajectory]
         served by  /move_group
         -> /moveit_simple_controller_manager             (move_group-internal client)
            -> /arm_controller/follow_joint_trajectory    [control_msgs/FollowJointTrajectory]
               served by  /arm_controller
               -> joint_trajectory_controller/JointTrajectoryController   (ros2_control)
                  -> /gz_ros_control hardware interface
                     -> Gazebo physics (this is what actually moves the joints)

Ownership was confirmed with `ros2 action info -t`:

    /execute_trajectory                  servers: /move_group
                                         clients: /move_to_pose_server, rviz2
    /arm_controller/follow_joint_trajectory
                                         servers: /arm_controller
                                         clients: /moveit_simple_controller_manager

| Layer | Owns | Can it stop a running trajectory? |
|---|---|---|
| MoveToPose (FlexCell) | validation, admission, result normalization, verification | yes, if it owns the goal |
| move_group `/execute_trajectory` | execution management, dispatch to the controller manager | **no - defect, see root cause** |
| `moveit_simple_controller_manager` | forwards the trajectory to the controller action | no |
| `arm_controller` (JointTrajectoryController) | interpolation, command interfaces | **yes - measured 51 ms** |
| `gz_ros_control` + Gazebo | applies commands to the simulated joints | n/a |

### Root cause

Source read: `moveit_ros/move_group/src/default_capabilities/execute_trajectory_action_capability.cpp`
at tag **2.12.4** - exactly the installed `ros-jazzy-moveit-ros-move-group 2.12.4`.

Two independent defects:

**1. The action server shares a MutuallyExclusive callback group with the blocking
execute callback.**
Lines 71-74 create `callback_group_` (MutuallyExclusive) on a dedicated executor;
line 84 passes that same group into `rclcpp_action::create_server`. While
`executePathCallback` blocks in
`context_->trajectory_execution_manager_->waitForExecution()` (line 126), the cancel
service callback cannot run. By the time it runs, the goal is already terminal, so
`rcl_action` reports `goals_canceling: 0`.

**2. The cancel path is never wired to the stop API.**
The cancel callback (line 82) only returns `CancelResponse::ACCEPT` - it stops nothing.
`preemptExecuteTrajectoryCallback()`, which would call
`trajectory_execution_manager_->stopExecution(true)`, is **dead code**: declared in
the `.hpp` (line 66), defined in the `.cpp` (line 151), and called from nowhere -
verified by grepping both the capability file and `move_group.cpp`.

`TrajectoryExecutionManager::stopExecution(bool auto_clear)` is a public API
(`trajectory_execution_manager.hpp:187`); nothing on the action cancel path invokes it.

Instrumented status trace of the failure (`test/execute_trajectory_cancel_trace.py`):

    [ 0.00s] EXEC_TRJ goal=678545d5 -> EXECUTING
    [ 0.01s] FJT      goal=59122139 -> EXECUTING
    CANCEL sent at 1.00s
             <no state transition whatsoever>
    [ 3.31s] FJT      goal=59122139 -> SUCCEEDED    <- controller ran the full 3.2 s
    [ 3.32s] EXEC_TRJ goal=678545d5 -> SUCCEEDED
    cancel response: goals_canceling=0

### Experiments

| # | Path | Cancel accepted? | Actual stop? | Stop latency | Final goal state | Reached original endpoint? |
|---|------|------------------|--------------|--------------|------------------|----------------------------|
| E1 | FlexCell MoveToPose -> `/execute_trajectory` (before fix) | no (`goals_canceling: 0`) | no | n/a | SUCCEEDED | **yes** (deviation 0.00000 rad) |
| E2 | direct `/execute_trajectory`, traced, bypassing FlexCell | no (`goals_canceling: 0`) | no | n/a | SUCCEEDED | **yes** (deviation 0.00000 rad) |
| E3 | direct `/arm_controller/follow_joint_trajectory` | **yes (`goals_canceling: 1`)** | **yes** | **0.051 s** | SUCCESSFUL (0) | **no** (deviation 0.623 rad) |
| E4 | FlexCell MoveToPose -> controller action (after fix) | yes (`goals_canceling: 1`) | yes | ~0.05 s | SUCCESSFUL (0) | **no** (deviation 2.909 rad) |

E2 vs E3 is the decisive pair: the *same* cancel request works at the controller layer
and is lost at the move_group layer.

### Final implementation

`MoveToPose` now dispatches execution through a selectable backend
(`execution_backend` parameter):

- **`controller_action` (default)** - FlexCell owns the controller goal, so cancel is
  real and measurable.
- `moveit_execute_trajectory` - the legacy path, retained for audit and comparison.
  It is **not cancellable** on MoveIt 2.12.4; do not use it where preemption matters.

MoveIt remains the planner (IK, collision-aware planning, time parameterization).
Only the execution dispatch moved.

### Stop semantics

`Result.stop_confirmed` is strict and requires **all five**:

1. a stop request was really sent to the component owning the trajectory
2. downstream accepted it (`goals_canceling >= 1`)
3. joint velocities actually reached rest
4. the robot did **not** reach the planned trajectory endpoint
5. the state could be re-read afterwards

`Result.preempted` is true only when (2) and (4) hold.

`stop_mode` records which case occurred:

| stop_mode | meaning | outcome |
|---|---|---|
| `preempted` | stop accepted and the motion was measurably cut short | `CANCELED` / `FAILED(EXECUTION_TIMEOUT)` |
| `already_completed` | the trajectory finished before the stop took effect; nothing was cut short | `CANCELED` / `FAILED(EXECUTION_TIMEOUT)`, `stop_confirmed=false` |
| `unconfirmed` | we cannot prove what happened | **`STATE_UNKNOWN`**, motion gate CLOSED |

A stationary robot alone is never treated as confirmation: a robot that finished its
trajectory is also stationary.

### Timeout semantics

    deadline reached
      -> STOPPING
      -> real stop request to the trajectory owner
      -> strict confirmation (as above)
      -> EXECUTION_TIMEOUT     (stop confirmed)
      -> STATE_UNKNOWN         (stop not confirmed), motion gate CLOSED

Measured: `deadline_ms=800` against a 3.7 s trajectory yields
`ERR_EXECUTION_TIMEOUT`, `preempted=true`, `stop_confirmed=true`,
detail `"timeout; preempted; stop confirmed"`.

## Known limitations

- The `moveit_execute_trajectory` backend remains non-cancellable (MoveIt 2.12.4
  defect documented above). It is not the default.
- No WorldState revision (gate disabled in Day 2 fixed-scene mode).
- No object-level verification, no pick/place, no Runtime Agent.
- Observed state comes from TF + `/joint_states` only.

## Structured log

JSON Lines at `~/.ros/flexcell/move_to_pose.jsonl`, one record per request:
request_id, action_goal_id, target, frame_id, motion_profile, timestamps,
validation result, IK pre-check, planning latency + raw MoveIt code,
execution start/end, feedback phases, stop reason + confirmation, final joint
state, reached pose, position/orientation error, outcome, FlexCell error code,
evidence_id.

