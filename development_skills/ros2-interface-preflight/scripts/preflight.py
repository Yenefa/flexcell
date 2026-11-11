"""Assert a RunComposite goal before paying for a simulator start.

Six interface mistakes in one session (see ../references/failure-cases.md) were all
static facts discoverable without Gazebo. This module separates the part that needs ROS
from the part that does not:

  validate_stage / validate_goal  pure, duck-typed, no ROS required, unit tested
  build_and_check                 imports the real messages, applies the same rules

The split matters because a checker that can only run where ROS exists cannot be tested
in CI, and an untested checker is one more thing to trust blindly.
"""
import sys

# The executor compares these exactly; see task_fsm_server "stages require world".
REQUIRED_FRAME = "world"
IDENTITY_QUAT = [0.0, 0.0, 0.0, 1.0]
MIN_STAGES = 1
MAX_STAGES = 8
TOLERANCE_RANGE = (0.0, 0.06)
CLEARANCE_RANGE = (0.05, 0.25)


def _quat(stage):
    q = stage.place_pose.pose.orientation
    return [q.x, q.y, q.z, q.w]


def validate_stage(stage):
    """Return a list of problems for one CompositeStage. Empty means acceptable."""
    problems = []
    sid = getattr(stage, "stage_id", "?")
    frame = getattr(stage.place_pose.header, "frame_id", None)
    if frame != REQUIRED_FRAME:
        problems.append("stage %r: header.frame_id is %r, executor requires %r"
                        % (sid, frame, REQUIRED_FRAME))
    quat = _quat(stage)
    if quat != IDENTITY_QUAT:
        problems.append("stage %r: orientation is %r, executor compares exactly to %r"
                        % (sid, quat, IDENTITY_QUAT))
    if not getattr(stage, "object_name", ""):
        problems.append("stage %r: empty object_name" % sid)
    return problems


def validate_goal(goal):
    problems = []
    stages = list(getattr(goal, "stages", []) or [])
    if not MIN_STAGES <= len(stages) <= MAX_STAGES:
        problems.append("%d stages; executor accepts %d..%d"
                        % (len(stages), MIN_STAGES, MAX_STAGES))
    for stage in stages:
        problems.extend(validate_stage(stage))
    objects = list(getattr(goal, "initial_objects", []) or [])
    if not objects:
        problems.append("initial_objects is empty; executor rejects it as "
                        "invalid initial object positions")
    for entry in objects:
        if not getattr(entry, "object_name", ""):
            problems.append("an initial_objects entry has empty object_name; "
                            "the field is object_name, not name")
    tol = getattr(goal, "position_tolerance_m", None)
    if not isinstance(tol, (int, float)) or isinstance(tol, bool):
        problems.append("position_tolerance_m is not a number")
    elif not TOLERANCE_RANGE[0] < tol <= TOLERANCE_RANGE[1]:
        problems.append("position_tolerance_m %r outside (0, %.2f]"
                        % (tol, TOLERANCE_RANGE[1]))
    clearance = getattr(goal, "clearance_m", None)
    if not isinstance(clearance, (int, float)) or isinstance(clearance, bool):
        problems.append("clearance_m is not a number")
    elif not CLEARANCE_RANGE[0] <= clearance <= CLEARANCE_RANGE[1]:
        problems.append("clearance_m %r outside [%.2f, %.2f]"
                        % (clearance, CLEARANCE_RANGE[0], CLEARANCE_RANGE[1]))
    return problems


def describe():
    """Print declared field names, so the next script is written from the truth."""
    from flexcell_interfaces.action import PushObject, RunComposite
    from flexcell_interfaces.msg import CompositeStage, ObjectPosition
    pairs = (("RunComposite.Goal", RunComposite.Goal),
             ("RunComposite.Result", RunComposite.Result),
             ("PushObject.Result", PushObject.Result),
             ("CompositeStage", CompositeStage),
             ("ObjectPosition", ObjectPosition))
    for label, msg in pairs:
        print("%-22s %s" % (label, sorted(msg.get_fields_and_field_types())))


def build_and_check():
    from flexcell_interfaces.action import RunComposite
    from flexcell_interfaces.msg import CompositeStage, ObjectPosition
    from geometry_msgs.msg import Point, PoseStamped
    goal = RunComposite.Goal()
    goal.scenario_id = "preflight"
    goal.motion_profile_id = "legacy"
    goal.position_tolerance_m = 0.02
    goal.clearance_m = 0.05
    goal.pause_after_stages = 0
    goal.resume_run_id = ""
    goal.resume_receipt_sha256 = ""
    op = ObjectPosition()
    op.object_name = "probe"          # NOT name
    op.position = Point(x=0.2, y=0.0, z=0.0175)
    goal.initial_objects = [op]
    stage = CompositeStage()
    stage.stage_id = "probe-0"
    stage.object_name = "probe"
    pose = PoseStamped()
    pose.header.frame_id = REQUIRED_FRAME
    pose.pose.position = Point(x=0.1, y=0.0, z=0.0175)
    pose.pose.orientation.x = 0.0
    pose.pose.orientation.y = 0.0
    pose.pose.orientation.z = 0.0
    pose.pose.orientation.w = 1.0
    stage.place_pose = pose
    goal.stages = [stage]
    goal.final_empty_positions = []
    return validate_goal(goal)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if "--describe" in argv:
        describe()
        return 0
    problems = build_and_check()
    if problems:
        print("PREFLIGHT_FAILED")
        for p in problems:
            print("  - " + p)
        return 1
    print("PREFLIGHT_OK -- safe to launch the simulator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
