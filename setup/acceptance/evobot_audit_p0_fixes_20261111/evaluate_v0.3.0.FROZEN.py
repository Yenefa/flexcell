#!/usr/bin/env python3
"""EvoBot independent task evaluator v0.1.

CONTRACT: evaluate(spec, final_state) -> verdict

The evaluator sees ONLY the task spec and the observed final state. It never reads
anything the agent wrote - no self-report, no log, no claim. An agent that says
"done" changes nothing here. Agent-reported success is not evidence.

It is a pure function and deterministic, so any third party can re-run it on the
same two inputs and get the same verdict. Every clause reports its own measured
number and threshold, so a failure is attributable instead of an opaque FAIL.
"""
import json
import math

# 0.3.0 adds the "push" goal clause (T08). It is a pure addition: a spec that does not
# declare "push" produces exactly the clause list it produced under 0.2.0, which is
# asserted by re-grading a frozen instance and comparing the verdict.
EVALUATOR_VERSION = "0.3.0"

# Declared tolerances. Changing one changes what "success" means, so the version
# string must change with them; the tests assert the pair stays in sync.
HORIZONTAL_TOLERANCE_M = 0.02
REST_HEIGHT_TOLERANCE_M = 0.02
UNMOVED_TOLERANCE_M = 0.015
STACK_TIER_HEIGHT_M = 0.030


def _dist2d(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _resting_z(spec, name):
    for obj in spec["objects"]:
        if obj["name"] == name:
            return obj["initial_pose"][2]
    return None


def _clause(name, ok, **evidence):
    return {"clause": name, "ok": bool(ok), "evidence": evidence}


def evaluate(spec, final_state):
    """Return a verdict dict. Pure function of its two arguments."""
    clauses = []
    pose = {name: list(p) for name, p in (final_state.get("objects") or {}).items()}
    initial = {o["name"]: list(o["initial_pose"]) for o in spec["objects"]}
    zones = {z["name"]: z for z in spec["zones"]}
    goal = spec["expected_goal"]

    for name, zone_name in sorted(goal.get("placement", {}).items()):
        if name not in pose:
            clauses.append(_clause("placement:" + name, False, reason="object missing"))
            continue
        if zone_name not in zones:
            clauses.append(_clause("placement:" + name, False, reason="unknown zone"))
            continue
        zone = zones[zone_name]
        d = _dist2d(pose[name], zone["pose"])
        inside = d <= zone["radius"]
        rest = _resting_z(spec, name)
        dz = None if rest is None else abs(pose[name][2] - rest)
        grounded = dz is not None and dz <= REST_HEIGHT_TOLERANCE_M
        clauses.append(_clause(
            "placement:" + name, inside and grounded,
            zone=zone_name, distance_m=round(d, 5), radius_m=zone["radius"],
            inside_zone=inside,
            height_error_m=None if dz is None else round(dz, 5),
            resting=grounded,
            final_pose=[round(v, 5) for v in pose[name]]))

    for name in goal.get("unmoved", []):
        if name not in pose:
            clauses.append(_clause("unmoved:" + name, False, reason="object missing"))
            continue
        if name not in initial:
            # The spec is inconsistent: it asks to protect an object it never
            # declares. Report that as a failure instead of crashing, so a bad
            # spec cannot take the evaluator down mid-batch.
            clauses.append(_clause("unmoved:" + name, False,
                                   reason="object not declared in spec"))
            continue
        d = _dist2d(pose[name], initial[name])
        clauses.append(_clause(
            "unmoved:" + name, d <= UNMOVED_TOLERANCE_M,
            distance_m=round(d, 5), tolerance_m=UNMOVED_TOLERANCE_M))

    required_order = list(goal.get("order") or [])
    if required_order:
        observed = [n for n in (final_state.get("move_sequence") or []) if n in required_order]
        seen, cursor, violations = [], 0, []
        for name in observed:
            if cursor < len(required_order) and name == required_order[cursor]:
                seen.append(name)
                cursor += 1
            elif name not in seen:
                violations.append(name)
        ok = cursor == len(required_order) and not violations
        clauses.append(_clause(
            "order", ok, required=required_order, observed=observed,
            matched=cursor, out_of_order=violations))

    # Relay clause: a template that says "pass through bin X first" must be checked on
    # the ROUTE, not only the final position. Without this a direct move would pass and
    # the template would not be testing what its instruction asks for.
    for name, required_zones in sorted((goal.get("visit") or {}).items()):
        seen = [v for v in (final_state.get("visits") or {}).get(name, [])]
        ok = all(z in seen for z in required_zones)
        clauses.append(_clause(
            "visit:" + name, ok, required=required_zones, observed=seen))

    # Ordered route clause. The set-based "visit" clause cannot distinguish a real
    # three-move chain from a two-move shortcut that happens to end in the right bin.
    # This is STRICTER (new clause), never a relaxation of an existing one.
    for name, required_seq in sorted((goal.get("visit_sequence") or {}).items()):
        observed = list((final_state.get("visits") or {}).get(name, []))
        ok = observed == list(required_seq)
        clauses.append(_clause(
            "visit_sequence:" + name, ok,
            required=list(required_seq), observed=observed))

    min_tiers = goal.get("min_tiers")
    if min_tiers:
        heights = sorted(pose[n][2] for n in goal.get("placement", {}) if n in pose)
        tiers = 0
        for i, z in enumerate(heights):
            if i == 0 or z - heights[i - 1] >= STACK_TIER_HEIGHT_M:
                tiers += 1
        clauses.append(_clause(
            "stacking", tiers >= min_tiers, tiers=tiers, required=min_tiers,
            heights=[round(z, 5) for z in heights]))

    # RELATIONAL clause: "X must end at a fixed offset from wherever Y ACTUALLY ended up".
    #
    # Why this is not a convenience: every other clause anchors to something declared in the
    # spec (a zone, an initial pose, an order). This one anchors to an ACHIEVED pose, which
    # carries execution error. A planner that never re-observes can only place X relative to
    # where it INTENDED to put Y, so it is wrong by exactly that error. It is therefore the
    # first goal shape in this benchmark that a blind one-shot plan cannot satisfy by
    # construction, and it exists to test whether the agent can acquire a procedure for it.
    #
    # It is pure, it reads only the final state, and it can only ADD a clause - no existing
    # clause is relaxed or removed.
    for rel in (goal.get("relative") or []):
        name = rel.get("object")
        ref = rel.get("reference")
        off = rel.get("offset") or [0.0, 0.0]
        tol = float(rel.get("tolerance_m", 0.01))
        label = "relative:%s@%s" % (name, ref)
        if name not in pose or ref not in pose:
            clauses.append(_clause(label, False,
                                   reason="object missing",
                                   missing=[n for n in (name, ref) if n not in pose]))
            continue
        want = (pose[ref][0] + float(off[0]), pose[ref][1] + float(off[1]))
        d = _dist2d(pose[name], want)
        clauses.append(_clause(
            label, d <= tol, distance_m=round(d, 5), tolerance_m=tol,
            reference_final=[round(v, 5) for v in pose[ref][:2]],
            required_delta=[float(off[0]), float(off[1])]))

    # PUSH clause (T08). A push task is distinguished from a pick-and-place task by
    # REQUIRING displacement and REQUIRING that the object not be lifted. Both halves are
    # needed: a displacement test alone is satisfied by carrying the object, and an
    # "unlifted" test alone is satisfied by doing nothing.
    #
    # This is a pure addition. No existing clause is relaxed, and a spec that does not
    # declare "push" evaluates exactly as before, so every frozen T01-T06 result stands.
    for name, want in sorted((goal.get("push") or {}).items()):
        label = "push:" + name
        if name not in pose:
            clauses.append(_clause(label, False, reason="object missing"))
            continue
        if name not in initial:
            clauses.append(_clause(label, False, reason="object not declared in spec"))
            continue
        start = initial[name]
        end = pose[name]
        dx, dy = end[0] - start[0], end[1] - start[1]
        moved = math.hypot(dx, dy)
        min_m = float(want.get("min_displacement_m", 0.030))
        max_m = float(want.get("max_displacement_m", 0.150))
        # Vertical displacement is checked separately: pushing must not become lifting.
        dz = abs(end[2] - start[2])
        max_dz = float(want.get("max_vertical_m", 0.020))
        # Direction: cosine against the required unit vector. Reported even when the
        # object barely moved, where the cosine is numerically meaningless -- the
        # displacement bound is what rejects that case, not the cosine.
        want_dir = want.get("direction")
        cos = None
        if want_dir and moved > 1e-9:
            n = math.hypot(float(want_dir[0]), float(want_dir[1]))
            cos = (dx * float(want_dir[0]) + dy * float(want_dir[1])) / (moved * n)
        min_cos = float(want.get("min_direction_cosine", 0.9))
        # A target zone, if given, is where the object must END UP; the displacement
        # bounds above are what distinguish a push from a carry.
        zone_ok = True
        zone_ev = {}
        if want.get("zone"):
            zn = want["zone"]
            if zn not in zones:
                zone_ok = False
                zone_ev = {"reason": "unknown zone", "zone": zn}
            else:
                d = _dist2d(end, zones[zn]["pose"])
                zone_ok = d <= zones[zn]["radius"]
                zone_ev = {"zone": zn, "distance_m": round(d, 5),
                           "radius_m": zones[zn]["radius"], "inside_zone": zone_ok}
        ok = (min_m <= moved <= max_m) and dz <= max_dz and zone_ok
        if cos is not None:
            ok = ok and cos >= min_cos
        clauses.append(_clause(
            label, ok,
            displacement_m=round(moved, 5), min_displacement_m=min_m,
            max_displacement_m=max_m, vertical_m=round(dz, 5),
            max_vertical_m=max_dz,
            direction_cosine=None if cos is None else round(cos, 5),
            min_direction_cosine=min_cos,
            **zone_ev))

    passed = bool(clauses) and all(c["ok"] for c in clauses)
    claimed = bool(final_state.get("agent_claimed_success"))
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "task_id": spec["task_id"],
        "template_id": spec["template_id"],
        "passed": passed,
        "clauses": clauses,
        "failed_clauses": [c["clause"] for c in clauses if not c["ok"]],
        "agent_claimed_success": claimed,
        "false_success": bool(claimed and not passed),
        "false_failure": bool(passed and not claimed),
    }


def evaluate_file(spec_path, state_path):
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)
    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)
    return evaluate(spec, state)


if __name__ == "__main__":
    import sys
    print(json.dumps(evaluate_file(sys.argv[1], sys.argv[2]), indent=2))
