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

## Known blocker: cancel cannot preempt execution

`MoveToPose` implements cancel correctly (phases reach `STOPPING`, the robot is
observed coming to rest, and the outcome is reported honestly). But it **cannot
reliably cut a motion short**, because the underlying API does not support it here.

Isolated test against `/execute_trajectory` directly, bypassing the FlexCell server
(`test/direct_execute_cancel_test.py`, cancel 1.0 s into a 2.98 s trajectory):

    cancel response: CancelGoal_Response   goals_canceling: 0
    execute result code: 1 (SUCCESS)
    max deviation from planned end: 0.00000 rad
    wall: 4.01 s

The cancel request is accepted at the ROS action layer but the goal is not in the
cancelable set; MoveIt 2.12.4 runs the trajectory to completion and returns
`SUCCESS`. The server therefore reports `stop_mode: already_completed` with
`max_deviation_from_planned_end_rad` as measured evidence, and never claims a
preemption it cannot prove.

Candidate remedies for a later day (not attempted here): verify whether
`move_group` exposes trajectory cancellation via a different path, check the
`trajectory_execution/allowed_execution_duration_scaling` / controller-side stop
options, or stop at the `ros2_control` layer.

## Known limitations

- No WorldState revision (gate disabled in Day 2 fixed-scene mode).
- No object-level verification, no pick/place, no Runtime Agent.
- `observed` state comes from TF + `/joint_states` only.

## Structured log

JSON Lines at `~/.ros/flexcell/move_to_pose.jsonl`, one record per request:
request_id, action_goal_id, target, frame_id, motion_profile, timestamps,
validation result, IK pre-check, planning latency + raw MoveIt code,
execution start/end, feedback phases, stop reason + confirmation, final joint
state, reached pose, position/orientation error, outcome, FlexCell error code,
evidence_id.

