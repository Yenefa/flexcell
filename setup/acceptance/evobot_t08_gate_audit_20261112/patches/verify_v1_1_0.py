#!/usr/bin/env python3
"""Fail-closed physical evidence verifier for T08 push - v1.1.0.

WHY THIS IS A NEW FILE AND NOT AN EDIT TO verify.py
    v1.0.0 graded every T08 result this round. The project's discipline is that a
    changed acceptance protocol becomes a new version and old results keep the
    version that graded them (evaluate_v0.3.0.FROZEN.py was preserved this way).
    verify.py v1.0.0 is left byte-identical.

WHAT v1.0.0 GOT WRONG (see ../../../setup/acceptance/evobot_t08_gate_audit_20261112/)
    v1.0.0 is fail-closed against an honest-but-broken recorder, but NOT against a
    fabricating producer. Two of its nine gates compare the object's height against
    a number the producer supplies (task.rest_height_m). Set that number equal to
    the object's own height and both gates measure zero. Demonstrated: a constant
    50 mm-high carry graded PUSHED with failed_gates=[]. Finding F1.

THE THREE FIXES, IN PRIORITY ORDER
    1 BIND THE REST HEIGHT TO THE TASK SPEC.
        verify(bundle, terminal, limits, spec) recomputes rest from
        spec.objects[target].initial_pose[2]. A declared rest that disagrees is a
        hard FAIL, not a warning. With no spec, the gate cannot decide and fails
        closed. Kills F1/F2.
    2 BIND THE BUNDLE TO THE RUN.
        task_sha256 must equal the sha256 of the spec file; run_id must equal the
        run_id the caller says it is grading; the execution window must contain the
        samples. Kills F6 (replay) and F7 (decorative window).
    3 RECOMPUTE THE DIGEST AND CHECK THE MANIFEST.
        bundle_sha256 is recomputed from content and must match; manifest.files must
        cover every declared input. Kills F4/F5.

THE GATE-LEVEL FIXES
    gripper      refuses a span of fewer than 2 samples (F8); a one-sample span
                 cannot show a close-carry-reopen, which is the gate's purpose.
    pusher       pusher_links must be a subset of the caller-supplied allow-list of
                 the robot's real links (F9); the floor cannot be declared a pusher.
    attachment   events must agree with attached_during_window (F15).
    dropped      a non-zero dropped_samples is a failed gate (F12): a bundle that
                 admits it lost samples has not shown the whole motion.

WHAT THIS DOES NOT CHANGE
    The nine gate names and their order are identical to v1.0.0, so a diff of gate
    output is readable. The frozen task thresholds (0.03/0.15/0.02/0.9/0.06) are not
    here at all - they stay in the terminal evaluator.

NOT ADDRESSED HERE (needs human approval, changes what success means)
    The gripper limit 0.002 rad. Its justification in fixtures.py is written in
    millimetres ("2 mm separates the two cleanly") but applied in radians. See
    MIGRATION.md section 4 / finding F18.
"""
import hashlib
import math
import os

try:
    from . import schema
except ImportError:                      # run as a script / plain import
    import schema

VERIFIER_VERSION = "1.1.0"

TABLE_SUPPORT_TOLERANCE_M = 0.010
TELEPORT_JUMP_M = 0.030

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
    """Gate 1: the frozen terminal clauses must have passed."""
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
    """Gate 2: the trajectory must be complete and internally valid."""
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


# --------------------------------------------------------------- FIX 1
def _spec_rest_height(spec, target_name):
    """The resting height the TASK declares. Never the producer's number."""
    if not isinstance(spec, dict):
        return None
    for obj in (spec.get("objects") or []):
        if isinstance(obj, dict) and obj.get("name") == target_name:
            pose = obj.get("initial_pose")
            if isinstance(pose, list) and len(pose) >= 3 and _finite_number(pose[2]):
                return float(pose[2])
    return None


def _gate_table_support(bundle, spec):
    """Gate 3: the target rested on the table for the whole window.

    v1.1.0: the reference height comes from the SPEC, not the bundle. v1.0.0 read
    bundle.task.rest_height_m, which the producer supplies - so a carry could
    declare its own height as 'rest' and measure zero (finding F1).
    """
    task = bundle.get("task") or {}
    target_name = task.get("target_object")
    declared = task.get("rest_height_m")
    spec_rest = _spec_rest_height(spec, target_name)
    if spec_rest is None:
        return _gate("table_support", False,
                     "no task spec supplied; the resting height cannot be "
                     "established independently of the bundle")
    if not _finite_number(declared) or abs(float(declared) - spec_rest) > 1e-9:
        return _gate("table_support", False,
                     "declared rest height %r disagrees with the task spec %r; a "
                     "bundle that defines its own resting height cannot testify "
                     "that the object rested" % (declared, spec_rest),
                     declared_rest_m=declared, spec_rest_m=spec_rest)
    entry = (bundle.get("objects") or {}).get(target_name)
    if not isinstance(entry, dict):
        return _gate("table_support", False,
                     "no target trajectory or rest height to judge support")
    positions = _positions(entry)
    if not positions:
        return _gate("table_support", False, "target trajectory is empty")
    airborne = [z for _sim, _x, _y, z in positions
                if abs(z - spec_rest) > TABLE_SUPPORT_TOLERANCE_M]
    ok = not airborne
    reason = None
    if not ok:
        reason = ("%d of %d samples are further than %.1f mm from the resting "
                  "height" % (len(airborne), len(positions),
                              TABLE_SUPPORT_TOLERANCE_M * 1000.0))
    return _gate("table_support", ok, reason,
                 off_table_samples=len(airborne),
                 tolerance_m=TABLE_SUPPORT_TOLERANCE_M,
                 rest_source="task_spec")


def _gate_protected_unmoved(bundle, tolerance_m=None):
    """Gate 3b: the protected object must not have been disturbed."""
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


def _gate_no_lift(bundle, max_lift_m, spec):
    """Gate 4: no prohibited lift, measured from the SPEC's rest height.

    v1.1.0: same fix as table_support. v1.0.0 computed max(z) - bundle_rest, so a
    producer could set bundle_rest to the carry height and measure zero lift.
    """
    if not _finite_number(max_lift_m):
        return _gate("no_lift", False, "no lift limit supplied")
    task = bundle.get("task") or {}
    target_name = task.get("target_object")
    spec_rest = _spec_rest_height(spec, target_name)
    if spec_rest is None:
        return _gate("no_lift", False,
                     "no task spec supplied; lift cannot be measured against an "
                     "independently established rest height")
    declared = task.get("rest_height_m")
    if not _finite_number(declared) or abs(float(declared) - spec_rest) > 1e-9:
        return _gate("no_lift", False,
                     "declared rest height %r disagrees with the task spec %r"
                     % (declared, spec_rest))
    entry = (bundle.get("objects") or {}).get(target_name)
    if not isinstance(entry, dict):
        return _gate("no_lift", False, "no target trajectory")
    positions = _positions(entry)
    if not positions:
        return _gate("no_lift", False, "target trajectory is empty")
    lift = max(z for _sim, _x, _y, z in positions) - spec_rest
    ok = lift <= float(max_lift_m)
    reason = None
    if not ok:
        reason = ("maximum lift %.5f m exceeds the allowed %.5f m"
                  % (lift, float(max_lift_m)))
    return _gate("no_lift", ok, reason,
                 max_lift_m=round(lift, 6), allowed_m=float(max_lift_m),
                 rest_source="task_spec")


def _gate_pusher_contact(bundle, allowed_links=None):
    """Gate 5: a declared pusher link actually touched the target.

    v1.1.0: pusher_links must be a subset of the caller's allow-list. v1.0.0 read
    the list from the bundle it was judging, so any body - including the floor -
    could be declared the pusher (finding F9).
    """
    contacts = bundle.get("contacts") or {}
    task = bundle.get("task") or {}
    declared = list(contacts.get("pusher_links") or [])
    if not declared:
        return _gate("pusher_contact", False,
                     "no pusher links declared; contact with any body would "
                     "count, including the floor")
    if allowed_links is not None:
        stray = sorted(set(declared) - set(allowed_links))
        if stray:
            return _gate("pusher_contact", False,
                         "declared pusher link(s) %r are not links of this robot; "
                         "a run cannot nominate the body it was pushed by"
                         % (stray,), allowed=sorted(allowed_links))
    targeted = set(declared)
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

    v1.1.0: a span of fewer than 2 samples is REFUSED. v1.0.0 computed
    travel = max - min, which is 0 for a one-sample span, so a bundle carrying a
    single reading passed a gate whose stated purpose is to detect a change
    (finding F8).
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
    if len(span) < 2:
        return _gate("gripper", False,
                     "gripper span has %d sample(s); a change cannot be measured "
                     "from fewer than two" % len(span), samples=len(span))
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

    v1.1.0: the event count must agree with the window flag. v1.0.0 range-checked
    events and never compared the two (finding F15).
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
    if events != 0:
        return _gate("no_attachment", False,
                     "%d attachment event(s) were recorded while the window flag "
                     "says none occurred; the two must agree" % events,
                     events=events)
    return _gate("no_attachment", True, None, events=events)


def _observed_max_jump(bundle):
    """Largest single-step xy displacement actually present in the samples."""
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

    Unchanged from v1.0.0 - this gate was already sound. It measures the jump from
    the samples rather than trusting the declared figure, requires the two to
    agree, and caps a self-declared threshold at its own physical bound.
    """
    teleport = bundle.get("teleport") or {}
    declared = teleport.get("max_single_step_jump_m")
    if not _finite_number(declared):
        return _gate("no_teleport", False,
                     "single-step jump was never measured; a run that did not "
                     "check for teleports cannot rule one out")
    threshold = teleport.get("jump_threshold_m", TELEPORT_JUMP_M)
    limit = float(threshold) if _finite_number(threshold) else TELEPORT_JUMP_M
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
        ok = False
        reason = ("declared max jump %.6f m disagrees with the measured %.6f m; "
                  "a record that contradicts its own samples cannot be relied "
                  "on" % (float(declared), measured))
    return _gate("no_teleport", ok, reason,
                 max_jump_m=round(worst, 6), threshold_m=limit,
                 declared_jump_m=round(float(declared), 6),
                 measured_jump_m=round(measured, 6))


# --------------------------------------------------------------- FIX 3
def _gate_integrity(bundle, spec_path=None):
    """Gate 0b: the bundle must be intact and bound to the task.

    NEW IN v1.1.0. v1.0.0 checked that bundle_sha256 was a string and nothing
    else, so any post-hoc edit was undetectable (finding F4), and the manifest
    completeness check existed but was never called (F5).
    """
    problems = []
    manifest = bundle.get("manifest") or {}
    stored = manifest.get("bundle_sha256")
    if not isinstance(stored, str):
        problems.append("manifest.bundle_sha256 missing")
    else:
        try:
            recomputed = schema.bundle_sha256(bundle)
        except (TypeError, ValueError) as exc:
            problems.append("bundle cannot be canonicalised: %s" % exc)
        else:
            if recomputed != stored:
                problems.append(
                    "manifest.bundle_sha256 does not match the bundle contents "
                    "(stored %s..., recomputed %s...); the record was altered "
                    "after sealing" % (stored[:12], recomputed[:12]))
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        problems.append("manifest.files missing or empty")
    task = bundle.get("task") or {}
    if spec_path is not None:
        if not os.path.isfile(spec_path):
            problems.append("task spec %r not found" % spec_path)
        else:
            actual = schema.sha256_file(spec_path)
            if task.get("task_sha256") != actual:
                problems.append(
                    "task.task_sha256 does not match the spec file (declared "
                    "%r, actual %r)" % (task.get("task_sha256"), actual))
    if problems:
        return _gate("integrity", False, "; ".join(problems[:4]),
                     problem_count=len(problems))
    return _gate("integrity", True, None, files_covered=len(files))


# --------------------------------------------------------------- FIX 2
def _gate_run_binding(bundle, expected_run_id=None):
    """Gate 0c: the bundle must describe the run it is claimed to describe.

    NEW IN v1.1.0. v1.0.0 never compared run_id or the execution window to
    anything, so one captured bundle replayed across unlimited trials (F6) and a
    window excluding every sample was accepted (F7).
    """
    problems = []
    run = bundle.get("run") or {}
    run_id = run.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        problems.append("run.run_id missing")
    elif expected_run_id is not None and run_id != expected_run_id:
        problems.append("run.run_id %r is not the run being graded (%r)"
                        % (run_id, expected_run_id))
    window = run.get("execution_window") or {}
    start = window.get("start_sim_ns")
    end = window.get("end_sim_ns")
    if not isinstance(start, int) or not isinstance(end, int):
        problems.append("execution_window bounds missing")
    else:
        for name, entry in (bundle.get("objects") or {}).items():
            if not isinstance(entry, dict):
                continue
            samples = entry.get("samples") or []
            if not samples:
                continue
            outside = [s for s in samples
                       if not (start <= int(s[1]) <= end)]
            if outside:
                problems.append(
                    "objects.%s has %d sample(s) outside the declared execution "
                    "window %d..%d" % (name, len(outside), start, end))
                break
    if problems:
        return _gate("run_binding", False, "; ".join(problems[:4]),
                     problem_count=len(problems))
    return _gate("run_binding", True, None, run_id=run_id)


def _gate_completeness(bundle):
    """Gate 0d: a bundle that admits it lost samples is not complete.

    NEW IN v1.1.0. dropped_samples was range-checked by the schema and read by no
    gate, so a bundle could declare 937 dropped samples and pass (F12).
    """
    problems = []
    for name, entry in (bundle.get("objects") or {}).items():
        if not isinstance(entry, dict):
            continue
        dropped = entry.get("dropped_samples")
        if not isinstance(dropped, int) or isinstance(dropped, bool):
            problems.append("objects.%s.dropped_samples missing" % name)
        elif dropped != 0:
            problems.append(
                "objects.%s dropped %d sample(s); a lossy capture cannot show "
                "what happened in the gaps" % (name, dropped))
    if problems:
        return _gate("completeness", False, "; ".join(problems[:4]),
                     problem_count=len(problems))
    return _gate("completeness", True, None)


GATE_ORDER = ("terminal", "integrity", "run_binding", "trajectory",
              "completeness", "table_support", "protected_unmoved",
              "no_lift", "pusher_contact", "gripper", "no_attachment",
              "no_teleport")


def verify(bundle, terminal, limits=None, spec=None, spec_path=None,
           expected_run_id=None, allowed_pusher_links=None):
    """Judge physical evidence. A gate that cannot be evaluated is FAILED.

    spec / spec_path / expected_run_id / allowed_pusher_links are the v1.1.0
    bindings. Omitting them does not weaken the verifier: each corresponding gate
    fails closed, because a binding that was not supplied cannot be checked.
    """
    limits = dict(limits or {})
    if not isinstance(bundle, dict):
        bundle = {}

    gates = [_gate_terminal(terminal),
             _gate_integrity(bundle, spec_path),
             _gate_run_binding(bundle, expected_run_id),
             _gate_trajectory(bundle)]
    if gates[3]["ok"]:
        gates += [
            _gate_completeness(bundle),
            _gate_table_support(bundle, spec),
            _gate_protected_unmoved(bundle, limits.get("protected_move_m")),
            _gate_no_lift(bundle, limits.get("max_lift_during_m"), spec),
            _gate_pusher_contact(bundle, allowed_pusher_links),
            _gate_gripper(bundle, limits.get("max_aperture_change_rad")),
            _gate_no_attachment(bundle),
            _gate_no_teleport(bundle),
        ]
    else:
        for name in GATE_ORDER[4:]:
            gates.append(_gate(name, False,
                               "not evaluable: the evidence bundle did not "
                               "validate"))

    failed = [g for g in gates if not g["ok"]]
    passed = not failed

    if passed:
        physical_outcome = PHYSICAL_PUSHED
        evidence_status = "COMPLETE"
        failure_reason = None
    elif gates[3]["ok"] and all(
            g["gate"] not in ("trajectory", "terminal", "integrity",
                              "run_binding") for g in failed):
        physical_outcome = PHYSICAL_NOT_PUSHED
        evidence_status = "COMPLETE_EVIDENCE_CONTRADICTS_PUSH"
        failure_reason = failed[0]["gate"] + ": " + (failed[0]["reason"] or "")
    else:
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
