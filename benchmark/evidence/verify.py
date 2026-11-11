#!/usr/bin/env python3
"""Fail-closed physical evidence verifier for T08 push.

WHAT THIS IS
    A second, independent judgement layer above the terminal evaluator. The
    terminal evaluator asks "did the object end up in the right place". This
    asks "do we have complete physical evidence that it got there by being
    pushed". A run must satisfy both.

WHY THE TERMINAL EVALUATOR IS NOT ENOUGH
    Terminal state cannot distinguish pushing from grasp-carry-place: lift the
    block, carry it the required distance, set it down at the same height, and
    every displacement check passes while the task ("without picking it up")
    was violated. v0.4.0 closed part of that with one max_z number, and one
    number is a thin defence - it is satisfied by any run that happens to stay
    low, including one where the block was never touched at all.

THE EIGHT GATES, AND WHY EACH IS SEPARATE
    Each gate answers a question the others cannot, and every one can fail
    alone. They are not summed into a score, because a high score with one
    missing channel is exactly the false pass this exists to stop.

      1 terminal        the frozen terminal clauses passed
      2 trajectory      complete, valid, monotonic, finite, both objects
      3 table_support   the object rested on the table, not in the air
      3b protected      the other object was not disturbed
      4 no_lift         it never left the table beyond the allowed lift
      5 pusher_contact  a declared pusher link actually touched it
      6 gripper         the gripper did not perform a grasp (aperture stable)
      7 no_attachment   no carry/detachable-joint event occurred
      8 no_teleport     it was not moved by external state mutation

THREE FIELDS, NOT ONE BOOLEAN
    physical_outcome  what the physics says happened (PUSHED / NOT_PUSHED)
    evidence_status   whether that could be established (COMPLETE / reasons)
    failure_reason    the first gate that failed, or null

    A single boolean loses the difference between "the robot did not push it"
    and "we cannot tell whether the robot pushed it". Those need different
    responses: the first is a robot problem, the second a measurement problem,
    and conflating them is how missing telemetry becomes a robot failure.

VERSIONING
    Versioned independently of the terminal evaluator. v0.3.0 and the 30 mm
    threshold are untouched; nothing here re-decides displacement.
"""

import math

try:
    from . import schema
except ImportError:                      # run as a script / plain import
    import schema

VERIFIER_VERSION = "1.0.0"

# Fixed PHYSICAL limits. These are not the task thresholds and do not replace
# them: the 30 mm displacement gate stays in the terminal evaluator, untouched.
TABLE_SUPPORT_TOLERANCE_M = 0.010   # how far off rest still counts as resting
TELEPORT_JUMP_M = 0.030             # one-step displacement no push can produce

PHYSICAL_PUSHED = "PUSHED"
PHYSICAL_NOT_PUSHED = "NOT_PUSHED"
PHYSICAL_UNKNOWN = "UNKNOWN"


def _gate(name, ok, reason=None, **evidence):
    return {"gate": name, "ok": bool(ok),
            "reason": None if ok else reason, "evidence": evidence}


def _finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(float(value)))


def _gate_terminal(terminal):
    """Gate 1: the frozen terminal clauses must have passed.

    This verifier does not re-decide them and has no opinion on the
    thresholds. It requires that they were evaluated AND passed, so that a
    physical layer cannot be used to smuggle a run past a failed terminal
    check.
    """
    if not isinstance(terminal, dict):
        return _gate("terminal", False,
                     "no terminal verdict supplied; the physical layer cannot "
                     "stand in for the terminal clauses")
    passed = terminal.get("passed")
    reason = None
    if passed is not True:
        reason = ("terminal evaluator did not pass (failed: %r)"
                  % (terminal.get("failed_clauses"),))
    return _gate("terminal", passed is True, reason,
                 evaluator_version=terminal.get("evaluator_version"),
                 passed=passed)


def _gate_trajectory(bundle):
    """Gate 2: the trajectory must be complete and internally valid.

    Any schema problem fails the gate. The schema is written so that everything
    it complains about is something that makes the evidence unusable.
    """
    problems = schema.validate(bundle)
    if problems:
        return _gate("trajectory", False,
                     "evidence bundle is not valid: " + "; ".join(problems[:4]),
                     problem_count=len(problems))
    objects = bundle.get("objects") or {}
    return _gate("trajectory", True, None,
                 objects=sorted(objects),
                 total_samples=sum(len(e.get("samples") or [])
                                   for e in objects.values()))


def _positions(entry):
    return [(int(s[1]), float(s[3]), float(s[4]), float(s[5]))
            for s in (entry.get("samples") or [])]


def _gate_table_support(bundle):
    """Gate 3: the target rested on the table for the whole window.

    WHY THIS IS NOT no_lift
        no_lift bounds the MAXIMUM height. Table support asks whether the
        object was ever airborne for a sustained stretch. An object lowered from
        above and set down passes a max-height check and was never pushed. This
        gate looks at the whole trace, not at one number.
    """
    task = bundle.get("task") or {}
    target_name = task.get("target_object")
    rest = task.get("rest_height_m")
    entry = (bundle.get("objects") or {}).get(target_name)
    if not isinstance(entry, dict) or not _finite_number(rest):
        return _gate("table_support", False,
                     "no target trajectory or rest height to judge support")
    positions = _positions(entry)
    if not positions:
        return _gate("table_support", False, "target trajectory is empty")
    airborne = [z for _sim, _x, _y, z in positions
                if abs(z - float(rest)) > TABLE_SUPPORT_TOLERANCE_M]
    ok = not airborne
    reason = None
    if not ok:
        reason = ("%d of %d samples are further than %.1f mm from the resting "
                  "height" % (len(airborne), len(positions),
                              TABLE_SUPPORT_TOLERANCE_M * 1000.0))
    return _gate("table_support", ok, reason,
                 off_table_samples=len(airborne),
                 tolerance_m=TABLE_SUPPORT_TOLERANCE_M)


def _gate_protected_unmoved(bundle, tolerance_m=None):
    """Gate 3b: the protected object must not have been disturbed.

    WHY THIS IS ITS OWN GATE
        T08 says "do not move the blue block". Every other gate looks only at
        the target, so an arm that shoved the blue block aside on its way to
        the red one passed all eight and was reported as a clean push. The
        protected object's trajectory was being COLLECTED and never read.

    WHY DISPLACEMENT AND NOT JUST FINAL POSITION
        An object nudged and nudged back ends where it started. The maximum
        excursion is what shows it was disturbed.
    """
    if not _finite_number(tolerance_m):
        tolerance_m = 0.005
    task = bundle.get("task") or {}
    name = task.get("protected_object")
    entry = (bundle.get("objects") or {}).get(name)
    if not isinstance(entry, dict):
        return _gate("protected_unmoved", False,
                     "no trajectory for the protected object %r; its safety was "
                     "never observed" % (name,))
    positions = _positions(entry)
    if not positions:
        return _gate("protected_unmoved", False,
                     "protected object trajectory is empty")
    x0, y0 = positions[0][1], positions[0][2]
    excursion = max(math.hypot(x - x0, y - y0) for _sim, x, y, _z in positions)
    ok = excursion <= float(tolerance_m)
    reason = None
    if not ok:
        reason = ("the protected object moved %.4f m, beyond the %.4f m "
                  "tolerance" % (excursion, float(tolerance_m)))
    return _gate("protected_unmoved", ok, reason,
                 max_excursion_m=round(excursion, 6),
                 tolerance_m=float(tolerance_m))


def _gate_no_lift(bundle, max_lift_m):
    """Gate 4: no prohibited lift.

    Uses the maximum over the WHOLE trace, not the end state. An object lifted
    and set back down ends at rest height; the max is the only place the lift
    is visible.
    """
    if not _finite_number(max_lift_m):
        return _gate("no_lift", False, "no lift limit supplied")
    task = bundle.get("task") or {}
    entry = (bundle.get("objects") or {}).get(task.get("target_object"))
    if not isinstance(entry, dict):
        return _gate("no_lift", False, "no target trajectory")
    positions = _positions(entry)
    if not positions:
        return _gate("no_lift", False, "target trajectory is empty")
    rest = float(task.get("rest_height_m"))
    lift = max(z for _sim, _x, _y, z in positions) - rest
    ok = lift <= float(max_lift_m)
    reason = None
    if not ok:
        reason = ("maximum lift %.5f m exceeds the allowed %.5f m"
                  % (lift, float(max_lift_m)))
    return _gate("no_lift", ok, reason,
                 max_lift_m=round(lift, 6), allowed_m=float(max_lift_m))


def _gate_pusher_contact(bundle):
    """Gate 5: a declared pusher link actually touched the target.

    WHY CONTACT AND NOT PROXIMITY
        Proximity is inference: "the arm was near the box and the box moved, so
        the arm must have pushed it". Contact is a measurement. The difference
        matters exactly in the case this gate exists for - an arm passing close
        by while something else moves the object.

    WHY CONTACT MUST OVERLAP THE DISPLACEMENT
        A contact interval somewhere in the window proves the arm touched the
        box at SOME point. It does not prove the touch caused the motion. The
        gate requires contact during the window in which the object moved.
    """
    contacts = bundle.get("contacts") or {}
    task = bundle.get("task") or {}
    targeted = set(contacts.get("pusher_links") or [])
    if not targeted:
        return _gate("pusher_contact", False,
                     "no pusher links declared; contact with any body would "
                     "count, including the floor")
    entry = (bundle.get("objects") or {}).get(task.get("target_object"))
    if not isinstance(entry, dict):
        return _gate("pusher_contact", False, "no target trajectory")
    positions = _positions(entry)
    if len(positions) < 2:
        return _gate("pusher_contact", False,
                     "trajectory too short to judge motion")

    motion = []
    for index in range(1, len(positions)):
        sim_now, x_now, y_now, _z = positions[index]
        _sim_prev, x_prev, y_prev, _z_prev = positions[index - 1]
        if math.hypot(x_now - x_prev, y_now - y_prev) > 1e-6:
            motion.append((positions[index - 1][0], sim_now))
    if not motion:
        return _gate("pusher_contact", False,
                     "the object never moved, so there is no push to attribute")

    intervals = [i for i in (contacts.get("intervals") or [])
                 if i.get("other") in targeted]
    if not intervals:
        return _gate("pusher_contact", False,
                     "no contact from a declared pusher link (%s): the object "
                     "moved without being touched by the pusher"
                     % sorted(targeted))
    overlapping = 0
    for start, end in motion:
        for interval in intervals:
            low = int(interval["start_sim_ns"])
            high = int(interval["end_sim_ns"])
            if low <= end and high >= start:
                overlapping += 1
                break
    if not overlapping:
        return _gate("pusher_contact", False,
                     "contact exists but never overlaps motion: the object "
                     "moved in %d windows, none during a pusher contact"
                     % len(motion),
                     motion_windows=len(motion),
                     contact_intervals=len(intervals))
    return _gate("pusher_contact", True, None,
                 motion_windows=len(motion),
                 overlapping_windows=overlapping,
                 contact_intervals=len(intervals),
                 pusher_links=sorted(targeted))


def _gate_gripper(bundle, max_aperture_change_rad):
    """Gate 6: the gripper did not perform a grasp during the window.

    WHY "NO GRASP" IS NOT "OPEN"
        The first version of this gate required the aperture to stay ABOVE a
        threshold, on the assumption that a non-grasping gripper is an open one.
        Real telemetry falsified that: on this robot a push is performed with
        the fingers CLOSED (measured aperture ~0.000 rad across all 937 samples
        of a real push). An open-only rule rejected every genuine push, which is
        the mirror image of the bug it was meant to prevent - a gate that fails
        everything is as useless as one that passes everything.

    WHAT ACTUALLY DISTINGUISHES A GRASP
        Not the aperture's absolute value but its MOTION. Grasping an object
        means the fingers close ON something: the aperture changes while the
        object is in hand, and the fingers stop against the object's width.
        A push with closed fingers holds a constant aperture. So the gate bounds
        the aperture's total variation, and the attachment gate separately rules
        out the arm being physically joined to the object.

    WHY IT STILL NEEDS THE WHOLE SPAN
        One reading cannot show a change. A close-carry-reopen would be visible
        only across the span, which is why the span must exist.
    """
    gripper = bundle.get("gripper") or {}
    if not _finite_number(max_aperture_change_rad):
        return _gate("gripper", False, "no calibrated aperture-change bound")
    joint = gripper.get("joint_name")
    span = gripper.get("span")
    if not isinstance(joint, str) or not joint:
        return _gate("gripper", False, "no gripper joint identified")
    if not isinstance(span, list) or not span:
        return _gate("gripper", False,
                     "no gripper aperture span recorded; one reading cannot "
                     "rule out a close-carry-reopen")
    values = []
    for item in span:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or not all(_finite_number(v) for v in item)):
            return _gate("gripper", False,
                         "gripper span contains a malformed sample")
        values.append(float(item[1]))
    travel = max(values) - min(values)
    ok = travel <= float(max_aperture_change_rad)
    reason = None
    if not ok:
        reason = ("gripper aperture changed by %.4f rad during the window "
                  "(limit %.4f); fingers closing on an object is a grasp, not "
                  "a push" % (travel, float(max_aperture_change_rad)))
    return _gate("gripper", ok, reason,
                 joint=joint, samples=len(values),
                 aperture_travel_rad=round(travel, 6),
                 limit_rad=float(max_aperture_change_rad),
                 min_aperture_rad=round(min(values), 6),
                 max_aperture_rad=round(max(values), 6))


def _gate_no_attachment(bundle):
    """Gate 7: no carry/detachable-joint event during the window.

    PHYSICAL, not logical: a DetachableJoint is how this stack actually makes
    the arm hold an object, so its presence is direct evidence of a carry
    rather than an inference from geometry.
    """
    attachment = bundle.get("attachment") or {}
    events = attachment.get("events")
    attached = attachment.get("attached_during_window")
    if attached is not False:
        return _gate("no_attachment", False,
                     "an attachment existed during the window; the object was "
                     "carried, not pushed")
    if not isinstance(events, int) or isinstance(events, bool) or events < 0:
        return _gate("no_attachment", False,
                     "attachment event count missing; absence of a count is not "
                     "evidence of absence of a carry")
    return _gate("no_attachment", True, None, events=events)


def _observed_max_jump(bundle):
    """Largest single-step xy displacement actually present in the samples.

    WHY THIS IS COMPUTED AND NOT READ FROM THE BUNDLE
        The bundle also carries teleport.max_single_step_jump_m. If the gate
        believed that number, a run could declare 5 mm while its own samples
        show an 80 mm jump, and the declaration would win. A claim about data
        must be checked against the data; that is the whole point of having it.

    WHY PER OBJECT AND NOT POOLED
        Concatenating two objects' samples invents a step between the last
        sample of one and the first of the other. Two boxes 4.8 m apart then
        look like a 4.8 m teleport, and every valid run is rejected. Measured
        here directly: a pooled version reported 4.8050 m for a clean push.
    """
    best = 0.0
    for entry in (bundle.get("objects") or {}).values():
        if not isinstance(entry, dict):
            continue
        positions = _positions(entry)
        for index in range(1, len(positions)):
            _sim_prev, x_prev, y_prev, _z_prev = positions[index - 1]
            _sim_now, x_now, y_now, _z_now = positions[index]
            best = max(best, math.hypot(x_now - x_prev, y_now - y_prev))
    return best


def _gate_no_teleport(bundle):
    """Gate 8: no single-step jump larger than any push could produce.

    WHY A JUMP AND NOT A SPEED
        A teleport (set_pose, external state mutation) moves the object between
        two physics steps with no time passing and no force applied. The
        signature is a displacement in ONE step beyond what contact can deliver.
        A push, however fast, accelerates the object through contact and
        produces a velocity, not a discontinuity.

    Both the declared figure and the measured one must be acceptable, and they
    must agree - otherwise the bundle has been altered or mis-recorded.
    """
    teleport = bundle.get("teleport") or {}
    declared = teleport.get("max_single_step_jump_m")
    if not _finite_number(declared):
        return _gate("no_teleport", False,
                     "single-step jump was never measured; a run that did not "
                     "check for teleports cannot rule one out")
    threshold = teleport.get("jump_threshold_m", TELEPORT_JUMP_M)
    limit = float(threshold) if _finite_number(threshold) else TELEPORT_JUMP_M
    # The declared limit may not exceed the verifier's own physical bound: a
    # run cannot widen the definition of "not a teleport" to admit one.
    if not _finite_number(threshold) or float(threshold) > TELEPORT_JUMP_M:
        limit = TELEPORT_JUMP_M
    measured = _observed_max_jump(bundle)
    worst = max(float(declared), measured)
    disagreement = abs(float(declared) - measured) > 1e-6
    ok = worst <= limit
    reason = None
    if not ok:
        reason = ("a single physics-step jump of %.4f m exceeds the %.4f m "
                  "threshold: the object was repositioned, not pushed"
                  % (worst, limit))
    elif disagreement:
        # Not a teleport, but the record does not match its own data.
        ok = False
        reason = ("declared max jump %.6f m disagrees with the measured %.6f m; "
                  "a record that contradicts its own samples cannot be relied "
                  "on" % (float(declared), measured))
    return _gate("no_teleport", ok, reason,
                 max_jump_m=round(worst, 6), threshold_m=limit,
                 declared_jump_m=round(float(declared), 6),
                 measured_jump_m=round(measured, 6))


def verify(bundle, terminal, limits=None):
    """Judge physical evidence.

    Returns physical_outcome / evidence_status / failure_reason plus per-gate
    detail. A gate that cannot be evaluated is a FAILED gate, never a skipped
    one: skipping on missing data is how a verifier quietly becomes a rubber
    stamp.
    """
    limits = dict(limits or {})
    if not isinstance(bundle, dict):
        bundle = {}
    gates = [_gate_terminal(terminal), _gate_trajectory(bundle)]
    if gates[1]["ok"]:
        gates += [
            _gate_table_support(bundle),
            _gate_protected_unmoved(bundle, limits.get("protected_move_m")),
            _gate_no_lift(bundle, limits.get("max_lift_during_m")),
            _gate_pusher_contact(bundle),
            _gate_gripper(bundle, limits.get("max_aperture_change_rad")),
            _gate_no_attachment(bundle),
            _gate_no_teleport(bundle),
        ]
    else:
        # A malformed bundle makes every downstream gate meaningless. Report
        # them as unevaluable rather than omitting them, so the output always
        # has one row per required evidence channel.
        for name in ("table_support", "protected_unmoved", "no_lift",
                     "pusher_contact", "gripper", "no_attachment",
                     "no_teleport"):
            gates.append(_gate(name, False,
                               "not evaluable: the evidence bundle did not "
                               "validate"))

    failed = [g for g in gates if not g["ok"]]
    passed = not failed

    if passed:
        physical_outcome = PHYSICAL_PUSHED
        evidence_status = "COMPLETE"
        failure_reason = None
    elif gates[1]["ok"] and all(
            g["gate"] not in ("trajectory", "terminal") for g in failed):
        # Evidence was readable, and the physics itself rules the push out.
        physical_outcome = PHYSICAL_NOT_PUSHED
        evidence_status = "COMPLETE_EVIDENCE_CONTRADICTS_PUSH"
        failure_reason = failed[0]["gate"] + ": " + (failed[0]["reason"] or "")
    else:
        # We could not establish what happened. This is NOT the same as "the
        # robot failed", and must not be reported as one.
        physical_outcome = PHYSICAL_UNKNOWN
        evidence_status = "INCOMPLETE_OR_INVALID_EVIDENCE"
        failure_reason = failed[0]["gate"] + ": " + (failed[0]["reason"] or "")

    return {
        "verifier_version": VERIFIER_VERSION,
        "physical_outcome": physical_outcome,
        "evidence_status": evidence_status,
        "failure_reason": failure_reason,
        "passed": passed,
        "gates": gates,
        "failed_gates": [g["gate"] for g in failed],
    }
