"""Canonical WorldState v2 serialization (M2.1, issue #3).

The ONE bridge between the ROS runtime and any decision policy: it converts
`flexcell_interfaces` msgs into the versioned policy-facing envelope and back.

Contract (ADR-002, ratified 2026-09-26):

    {"WorldStateSchemaVersion": 2, "world_state": {...}, "task_context": {...}}

- Deterministic: fixed field order, `sort_keys=True`, compact separators,
  floats rounded to 9 decimals, UTF-8. Same inputs -> byte-identical output.
- Fair: byte-identical bytes go to EVERY policy (FSM / Jev / LLM / Hybrid);
  `notes[]` (free-text diagnostics) is stripped and never serialized.
- Versioned (ratified ①): every envelope carries `WorldStateSchemaVersion`;
  `deserialize_envelope` refuses unknown versions instead of guessing.
  Old recordings stay replayable through version adapters added here.

This module is pure python: it duck-types msg objects and never imports rclpy,
so the contract is unit-testable offline.
"""

import json

SCHEMA_VERSION = 2
SCHEMA_VERSION_KEY = "WorldStateSchemaVersion"

# WorldState.msg v2 field that the executor owns at decide() time (ADR-002);
# observe_server publishes it default-empty and it never blocks serialization.
TASK_FIELD = "task"


class UnsupportedSchemaVersionError(ValueError):
    """Raised when an envelope's WorldStateSchemaVersion is not exactly ours."""


def _f(x):
    """Deterministic float: rounded to 1e-9 ( metre-level poses, rad, seconds)."""
    return round(float(x), 9)


def _pose_to_dict(pose):
    return {
        "position": {
            "x": _f(pose.position.x),
            "y": _f(pose.position.y),
            "z": _f(pose.position.z),
        },
        "orientation": {
            "x": _f(pose.orientation.x),
            "y": _f(pose.orientation.y),
            "z": _f(pose.orientation.z),
            "w": _f(pose.orientation.w),
        },
    }


def _point_to_dict(point):
    return {"x": _f(point.x), "y": _f(point.y), "z": _f(point.z)}


def _header_to_dict(header):
    return {
        "stamp": {"sec": int(header.stamp.sec), "nanosec": int(header.stamp.nanosec)},
        "frame_id": header.frame_id,
    }


def robot_to_dict(robot):
    """RobotStateSummary -> dict (v2: + gripper aperture)."""
    return {
        "joint_names": list(robot.joint_names),
        "positions": [_f(v) for v in robot.positions],
        "ee_pose": _pose_to_dict(robot.ee_pose),
        "ee_frame": robot.ee_frame,
        "gripper_joint_name": robot.gripper_joint_name,
        "gripper_position": _f(robot.gripper_position),
        "has_gripper_state": bool(robot.has_gripper_state),
    }


def object_to_dict(obj):
    """WorldObject -> dict (v2: + klass, + pose_age_s)."""
    return {
        "name": obj.name,
        "klass": obj.klass,
        "pose": _pose_to_dict(obj.pose),
        "size": [_f(v) for v in obj.size],
        "available": bool(obj.available),
        "pose_age_s": _f(obj.pose_age_s),
    }


def carry_to_dict(carry):
    """CarryState -> dict. Backend BELIEF - never physical evidence (ADR-001)."""
    return {
        "engaged": bool(carry.engaged),
        "object_id": carry.object_id,
        "reference_frame": carry.reference_frame,
        "offset": [_f(v) for v in carry.offset],
    }


def zone_to_dict(zone):
    """ZoneState -> dict (v2: + occupied_by)."""
    return {
        "id": zone.id,
        "center": _point_to_dict(zone.center),
        "radius": _f(zone.radius),
        "occupancy": int(zone.occupancy),
        "occupied_by": zone.occupied_by,
    }


def assignment_to_dict(a):
    return {
        "object_id": a.object_id,
        "zone_id": a.zone_id,
        "outcome": int(a.outcome),
        "error_code": int(a.error_code),
    }


def constraints_to_dict(c):
    """TaskConstraints -> dict. Executor-owned limits; policy consumes only."""
    return {
        "allowed_actions": list(c.allowed_actions),
        "recovery_budget": int(c.recovery_budget),
        "verify_tolerance_m": _f(c.verify_tolerance_m),
        "motion_profile_id": c.motion_profile_id,
        "max_world_age_s": _f(c.max_world_age_s),
    }


def history_entry_to_dict(h):
    return {
        "seq": int(h.seq),
        "action": h.action,
        "target": h.target,
        "outcome": int(h.outcome),
        "error_code": int(h.error_code),
        "attempt": int(h.attempt),
        "world_revision": int(h.world_revision),
        "evidence_id": h.evidence_id,
    }


def task_context_to_dict(tc):
    """TaskContext -> dict (v2: constraints + history included)."""
    return {
        "task_state": tc.task_state,
        "goal_id": tc.goal_id,
        "scenario_id": tc.scenario_id,
        "plan_remaining": [assignment_to_dict(a) for a in tc.plan_remaining],
        "plan_completed": [assignment_to_dict(a) for a in tc.plan_completed],
        "retry_counts": [int(v) for v in tc.retry_counts],
        "recovery_budget_remaining": int(tc.recovery_budget_remaining),
        "last_action": tc.last_action,
        "last_outcome": int(tc.last_outcome),
        "last_error_code": int(tc.last_error_code),
        "last_action_world_revision": int(tc.last_action_world_revision),
        "available_actions": list(tc.available_actions),
        "deadline_remaining_s": _f(tc.deadline_remaining_s),
        "fault_injection_active": bool(tc.fault_injection_active),
        "constraints": constraints_to_dict(tc.constraints),
        "history": [history_entry_to_dict(h) for h in tc.history],
    }


def world_state_to_dict(ws):
    """WorldState -> dict. Excludes `notes` (B1: free text never reaches a
    policy) and `task` (it is serialized as the envelope's own part)."""
    return {
        "header": _header_to_dict(ws.header),
        "revision": int(ws.revision),
        "source": ws.source,
        "schema_version": ws.schema_version,
        "robot": robot_to_dict(ws.robot),
        "objects": [object_to_dict(o) for o in ws.objects],
        "carry": carry_to_dict(ws.carry),
        "zones": [zone_to_dict(z) for z in ws.zones],
    }


def build_envelope(ws, tc=None):
    """WorldState (+ optional TaskContext override) -> the versioned envelope.

    `tc=None` uses `ws.task` (executor-owned field; observe publishes it
    default-empty and the executor overwrites it at decide() time).
    """
    task = tc if tc is not None else ws.task
    return {
        SCHEMA_VERSION_KEY: SCHEMA_VERSION,
        "world_state": world_state_to_dict(ws),
        "task_context": task_context_to_dict(task),
    }


def serialize_dict(envelope):
    """Envelope dict -> deterministic JSON text (sort_keys, compact, strict)."""
    return json.dumps(
        envelope, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False)


def serialize_envelope(ws, tc=None):
    """WorldState + TaskContext msgs -> deterministic policy-facing JSON text."""
    return serialize_dict(build_envelope(ws, tc))


def deserialize_envelope(text):
    """JSON text -> envelope dict, refusing unknown schema versions.

    Ratified ①: readers dispatch or refuse explicitly; they never silently
    interpret a recording produced under a different WorldStateSchemaVersion.
    """
    env = json.loads(text)
    version = env.get(SCHEMA_VERSION_KEY)
    if version != SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            "policy input has %s=%r, this reader speaks %r - use the matching "
            "version adapter" % (SCHEMA_VERSION_KEY, version, SCHEMA_VERSION))
    return env


def _missing(container, required, prefix, violations):
    for key in required:
        if key not in container:
            violations.append("%s.%s missing" % (prefix, key))


def validate_envelope(env):
    """Structural validation; returns a list of violation paths (empty = valid).

    Required-fields check per issue #3: every field a policy may rely on must
    be present with the right type. Extra fields are allowed (additive schema
    evolution), wrong-absent fields are not.
    """
    v = []
    if env.get(SCHEMA_VERSION_KEY) != SCHEMA_VERSION:
        v.append("%s must be %r" % (SCHEMA_VERSION_KEY, SCHEMA_VERSION))
        return v

    ws = env.get("world_state")
    if not isinstance(ws, dict):
        v.append("world_state must be an object")
        return v
    _missing(ws, ("header", "revision", "source", "schema_version",
                  "robot", "objects", "carry", "zones"), "world_state", v)
    if not isinstance(ws.get("revision"), int) or ws["revision"] < 0:
        v.append("world_state.revision must be a non-negative integer")
    if not isinstance(ws.get("source"), str) or not ws["source"]:
        v.append("world_state.source must be a non-empty string")
    robot = ws.get("robot")
    if isinstance(robot, dict):
        _missing(robot, ("joint_names", "positions", "ee_pose", "ee_frame"),
                 "world_state.robot", v)
    else:
        v.append("world_state.robot must be an object")
    objects = ws.get("objects")
    if isinstance(objects, list):
        for i, obj in enumerate(objects):
            if isinstance(obj, dict):
                _missing(obj, ("name", "pose", "available"),
                         "world_state.objects[%d]" % i, v)
            else:
                v.append("world_state.objects[%d] must be an object" % i)
    else:
        v.append("world_state.objects must be an array")
    carry = ws.get("carry")
    if isinstance(carry, dict):
        _missing(carry, ("engaged", "object_id", "reference_frame", "offset"),
                 "world_state.carry", v)
    else:
        v.append("world_state.carry must be an object")
    zones = ws.get("zones")
    if isinstance(zones, list):
        for i, zone in enumerate(zones):
            if isinstance(zone, dict):
                _missing(zone, ("id", "center", "radius", "occupancy"),
                         "world_state.zones[%d]" % i, v)
                if "occupancy" in zone and zone["occupancy"] not in (-1, 0, 1):
                    v.append("world_state.zones[%d].occupancy must be -1/0/1" % i)
            else:
                v.append("world_state.zones[%d] must be an object" % i)
    else:
        v.append("world_state.zones must be an array")

    tc = env.get("task_context")
    if not isinstance(tc, dict):
        v.append("task_context must be an object")
        return v
    _missing(tc, ("task_state", "goal_id", "scenario_id", "plan_remaining",
                  "plan_completed", "retry_counts", "recovery_budget_remaining",
                  "available_actions", "deadline_remaining_s",
                  "fault_injection_active", "constraints", "history"),
             "task_context", v)
    constraints = tc.get("constraints")
    if isinstance(constraints, dict):
        _missing(constraints, ("allowed_actions", "recovery_budget",
                               "verify_tolerance_m", "motion_profile_id",
                               "max_world_age_s"),
                 "task_context.constraints", v)
    else:
        v.append("task_context.constraints must be an object")
    history = tc.get("history")
    if isinstance(history, list):
        for i, entry in enumerate(history):
            if isinstance(entry, dict):
                _missing(entry, ("seq", "action", "outcome"),
                         "task_context.history[%d]" % i, v)
            else:
                v.append("task_context.history[%d] must be an object" % i)
    else:
        v.append("task_context.history must be an array")
    return v


def validate_or_raise(env):
    """validate_envelope that raises ValueError on the first violation batch."""
    violations = validate_envelope(env)
    if violations:
        raise ValueError("invalid envelope: " + "; ".join(violations))
    return env
