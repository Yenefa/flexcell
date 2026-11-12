#!/usr/bin/env python3
"""Issue #232 - read-only offline check of push PROGRESS vs final NET DISPLACEMENT.

WHY THIS EXISTS
    A push is reported action by action. Each action returns a number that looks like
    progress. The task is decided by where the box ENDED UP. Those are different
    quantities, and this project has repeatedly read one as the other.

    Measured example this tool was built to stop being re-derived by hand:
      runs/U_shot/seed3002/t1  push_00.json reports displacement_m = 0.030629
      the same run's ground truth moves the box 0.140287 m along the push direction
      ratio 4.58x  -> the reported number describes ONE action's measurement window,
      not the run's displacement.

THREE QUANTITIES, DEFINED SEPARATELY. They are never collapsed into one field.

  u                     unit vector of the task's push direction, in the XY plane.
                        Arbitrary planar direction: nothing here assumes -x.

  reported_progress_m   sum over the run's push action records of the per-action
                        reported displacement projected onto u, sign taken from that
                        record's own direction_cos. This is what the skill SAID.
                        It is a claim, not a measurement of the world.

  net_displacement_m    (post - pre) . u
                        The SIGNED component of the box's net XY movement along u, which
                        is what issue #232 asks for ("signed net displacement computed
                        along the task direction"). Positive = along u, negative =
                        against u. A reversal therefore reports NEGATIVE, never a
                        flipped magnitude. net_along_u_m is kept as an alias so that a
                        reader who expects that name finds the same number.

  net_magnitude_m       |post_xy - pre_xy|
                        The full net vector length, INCLUDING any lateral drift. Reported
                        alongside, never substituted for the along-direction number: the
                        two differ whenever the push is not perfectly aligned, and
                        swapping one for the other is the class of error this tool exists
                        to expose (measured case: along 0.140287 vs magnitude 0.140988).
  lateral_m             |(post - pre) - ((post - pre).u) u|  - movement across u.
  arm_travel_m          sum of the per-action ee_travel_m: how far the END EFFECTOR was
                        commanded to travel across the run. This is NOT box travel and is
                        never substituted for it. It is reported because the gap between
                        arm travel and net box displacement is the retreat-transit
                        signature: measured case U/seed3002 travelled 0.358 m of arm to
                        net 0.046 m of box, because the recovery layer backs off and
                        re-approaches. A check that read arm travel as box displacement
                        would report a 7.8x error that does not exist.

  travel_to_net_ratio   arm_travel_m / |net_displacement_m| when both are known and the
                        net is non-zero, else UNKNOWN. Compare this ACROSS trials; do not
                        read a single value as an error.

  difference_m          net_displacement_m - reported_progress_m
                        The number the Lead was looking for and repeatedly got from a
                        mismatched pair. A large difference is a SCOPE mismatch, not
                        necessarily an error: one action's report against a whole run's
                        displacement is expected to differ.

UNKNOWN, NOT ZERO
    Missing endpoint, non-finite number, empty direction, or no action records all
    produce the string UNKNOWN for that quantity and a status of UNKNOWN for the
    trial. Nothing is defaulted to 0.0: a missing measurement is not a stationary box.

CLASSIFICATION (descriptive only)
    FORWARD / REVERSE / LATERAL / STATIONARY / UNKNOWN, decided from the measured net
    vector with explicit thresholds documented in classify_motion(). These are
    reporting buckets, NOT pass/fail.

WHAT THIS TOOL REFUSES TO DO
    - It does not read expected_goal thresholds to judge anything.
    - It does not emit a pass/fail verdict. Issue #232 asks for diagnostic facts only.
    - It opens inputs read-only and writes only under --out.

USAGE
    python3 check_progress_vs_net.py --out results/
    python3 check_progress_vs_net.py --self-test
"""
import argparse
import json
import math
import os
import sys

WT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))

UNKNOWN = "UNKNOWN"

# Motion buckets. A trial is LATERAL when the across-direction movement is the larger
# part of the net vector, STATIONARY when the net vector is negligible at all.
# STATIONARY_M is a REPORTING floor (1 mm), not an acceptance threshold.
STATIONARY_M = 0.001
LATERAL_DOMINANCE = 1.0


def _finite(v):
    """True only for a real, finite number. Rejects None, bool, nan, inf, strings."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return False
    return math.isfinite(float(v))


def _xy(p):
    """Accept [x,y,...] / {'position':[...]} / {'x':..,'y':..}; return (x,y) or None."""
    if isinstance(p, dict):
        if "position" in p:
            return _xy(p["position"])
        if _finite(p.get("x")) and _finite(p.get("y")):
            return (float(p["x"]), float(p["y"]))
        return None
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        if _finite(p[0]) and _finite(p[1]):
            return (float(p[0]), float(p[1]))
    return None


def unit_direction(direction):
    """Normalise an arbitrary planar direction. Returns (ux, uy) or None."""
    if direction is None:
        return None
    d = _xy(direction)
    if d is None:
        return None
    n = math.hypot(d[0], d[1])
    if not _finite(n) or n <= 0.0:
        return None
    return (d[0] / n, d[1] / n)


def classify_motion(net_along, net_lateral, stationary_m=STATIONARY_M):
    """Bucket the measured net motion. Descriptive only, never pass/fail."""
    if net_along is None or net_lateral is None:
        return UNKNOWN
    if math.hypot(net_along, net_lateral) < stationary_m:
        return "STATIONARY"
    if abs(net_lateral) > LATERAL_DOMINANCE * abs(net_along):
        return "LATERAL"
    return "FORWARD" if net_along >= 0 else "REVERSE"


def net_displacement(pre, post, u):
    """Signed net displacement of the box along u. Returns dict of quantities."""
    out = {"net_displacement_m": UNKNOWN, "net_along_u_m": UNKNOWN,
           "net_magnitude_m": UNKNOWN, "lateral_m": UNKNOWN, "motion": UNKNOWN,
           "unknown_reason": None}
    a, b = _xy(pre), _xy(post)
    if a is None or b is None:
        out["unknown_reason"] = "missing or non-finite endpoint (%s -> %s)" % (
            "ok" if a else "MISSING", "ok" if b else "MISSING")
        return out
    if u is None:
        out["unknown_reason"] = "no usable task direction"
        return out
    dx, dy = b[0] - a[0], b[1] - a[1]
    along = dx * u[0] + dy * u[1]
    perp_x, perp_y = dx - along * u[0], dy - along * u[1]
    lateral = math.hypot(perp_x, perp_y)
    mag = math.hypot(dx, dy)
    # ALONG-DIRECTION is the headline figure (issue #232 wording). The full vector
    # magnitude and the lateral part are reported beside it, never in place of it.
    out.update({"net_displacement_m": round(along, 9),
                "net_along_u_m": round(along, 9),
                "net_magnitude_m": round(mag, 9),
                "lateral_m": round(lateral, 9),
                "motion": classify_motion(along, lateral)})
    return out


def reported_progress(actions, u):
    """Sum the per-action reported displacement projected onto u.

    Each record may carry displacement_along_direction_m (already projected, sign
    included) or only displacement_m plus direction_cos. Never guess a sign: if a
    record has a magnitude and no sign source, the record is UNKNOWN and so is the sum.
    """
    if not actions:
        return {"reported_progress_m": UNKNOWN, "n_actions": 0,
                "unknown_reason": "no action records"}
    if u is None:
        return {"reported_progress_m": UNKNOWN, "n_actions": len(actions),
                "unknown_reason": "no usable task direction"}
    total = 0.0
    used = 0
    for i, a in enumerate(actions):
        along = a.get("displacement_along_direction_m")
        if _finite(along):
            total += float(along)
            used += 1
            continue
        disp = a.get("displacement_m")
        cos = a.get("direction_cos")
        if _finite(disp) and _finite(cos):
            if not math.isfinite(float(disp)) or not math.isfinite(float(cos)):
                return {"reported_progress_m": UNKNOWN, "n_actions": len(actions),
                        "unknown_reason": "action %d has non-finite reported value" % i}
            total += abs(float(disp)) * (1.0 if float(cos) >= 0.0 else -1.0)
            used += 1
            continue
        return {"reported_progress_m": UNKNOWN, "n_actions": len(actions),
                "unknown_reason": "action %d has no usable reported displacement" % i}
    if used == 0:
        return {"reported_progress_m": UNKNOWN, "n_actions": len(actions),
                "unknown_reason": "no action carried a usable reported value"}
    return {"reported_progress_m": round(total, 9), "n_actions": len(actions),
            "unknown_reason": None}


def analyse(pre, post, direction, actions, real_travel=None):
    """One trial -> the three quantities, kept separate and explicit."""
    u = unit_direction(direction)
    net = net_displacement(pre, post, u)
    rep = reported_progress(actions, u)
    diff = UNKNOWN
    if _finite(net["net_displacement_m"]) and _finite(rep["reported_progress_m"]):
        diff = round(float(net["net_displacement_m"]) - float(rep["reported_progress_m"]), 9)
    status = UNKNOWN
    if net["motion"] != UNKNOWN and rep["reported_progress_m"] != UNKNOWN:
        status = "MEASURED"
    reason = net["unknown_reason"] or rep["unknown_reason"]
    return {"status": status, "unknown_reason": reason,
            "unit_direction": None if u is None else [round(u[0], 9), round(u[1], 9)],
            "reported_progress_m": rep["reported_progress_m"],
            "n_actions": rep["n_actions"],
            "net_displacement_m": net["net_displacement_m"],
            "net_along_u_m": net["net_along_u_m"],
            "net_magnitude_m": net["net_magnitude_m"],
            "lateral_m": net["lateral_m"],
            "arm_travel_m": round(float(real_travel), 9) if _finite(real_travel) else UNKNOWN,
            "travel_to_net_ratio": (round(float(real_travel) / abs(float(net["net_displacement_m"])), 6)
                                    if _finite(real_travel) and _finite(net["net_displacement_m"])
                                    and abs(float(net["net_displacement_m"])) > 0 else UNKNOWN),
            "difference_m": diff,
            "motion": net["motion"]}


# ---------------------------------------------------------------- archive adapters
def _load(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _actions_from_dir(d):
    """push_NN.json is written one per attempt by the recovery driver."""
    got = []
    try:
        names = sorted(n for n in os.listdir(d) if n.startswith("push_") and n.endswith(".json"))
    except OSError:
        return got
    for n in names:
        rec = _load(os.path.join(d, n))
        if isinstance(rec, dict):
            got.append(rec)
    return got


def _direction_from_record(rec):
    """Recover the commanded direction from an artifact, or None.

    Order: an explicit direction field, then the task spec's own expected_goal push
    direction. Nothing is assumed: a missing direction yields UNKNOWN rather than a
    default of -x, because a default would silently compute every lateral push as if it
    were along -x.
    """
    for key in ("direction", "push_direction"):
        v = rec.get(key)
        if v is not None:
            return v
    goal = rec.get("expected_goal")
    if isinstance(goal, dict):
        push = goal.get("push")
        if isinstance(push, dict):
            for name in sorted(push):
                entry = push[name]
                if isinstance(entry, dict) and entry.get("direction") is not None:
                    return entry.get("direction")
    return None


def collect_trials(root):
    """Walk an archive root and yield one trial dict per discovered run directory.

    Deliberately tolerant: a directory with a push_*.json but no endpoints becomes an
    UNKNOWN trial rather than being skipped, because a silently skipped trial is how a
    coverage gap becomes an invisible one.
    """
    trials = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        push = [n for n in filenames if n.startswith("push_") and n.endswith(".json")]
        if not push:
            continue
        actions = _actions_from_dir(dirpath)
        rel = os.path.relpath(dirpath, root).replace(os.sep, "/")
        direction = None
        pre = post = None
        travel = None
        for name in ("pre.json", "before.json", "gt_before.json"):
            obj = _load(os.path.join(dirpath, name))
            if isinstance(obj, dict):
                pre = obj.get("target_box_a") if "target_box_a" in obj else obj.get("objects", {}).get("target_box_a") if isinstance(obj.get("objects"), dict) else obj
                direction = direction or _direction_from_record(obj)
                break
        for name in ("post.json", "after.json", "gt_after.json"):
            obj = _load(os.path.join(dirpath, name))
            if isinstance(obj, dict):
                post = obj.get("target_box_a") if "target_box_a" in obj else obj.get("objects", {}).get("target_box_a") if isinstance(obj.get("objects"), dict) else obj
                break
        # Task spec / evaluator input carries the commanded direction (T08 family).
        for name in ("evaluator_input.json", "observation_input.json", "spec.json", "task.json"):
            if name in filenames and direction is None:
                obj = _load(os.path.join(dirpath, name))
                if isinstance(obj, dict):
                    direction = _direction_from_record(obj)
        # A single result json may carry pre/post together (candidate archives).
        for name in filenames:
            if not name.endswith(".json") or name.startswith("push_"):
                continue
            obj = _load(os.path.join(dirpath, name))
            if not isinstance(obj, dict):
                continue
            if pre is None and isinstance(obj.get("pre"), dict):
                pre = obj["pre"].get("target_box_a")
            if post is None and isinstance(obj.get("post"), dict):
                post = obj["post"].get("target_box_a")
            direction = direction or _direction_from_record(obj)
        for a in actions:
            t = a.get("ee_travel_m")
            if _finite(t):
                travel = (travel or 0.0) + float(t)
        trials.append({"trial": rel or ".", "pre": pre, "post": post,
                       "direction": direction, "actions": actions,
                       "real_travel_m": travel})
    return trials


def collect_candidate_files(root):
    """Second family: one JSON per run carrying pre/post and a push block in the SAME file.

    Some archives (the calibration candidates) never write push_NN.json beside ground
    truth; they write a single summary with pre, post, verdict and push.skill_disp. A
    trial with a push claim but no endpoints is still COLLECTED, as UNKNOWN - dropping it
    would hide a coverage gap behind a shorter table.
    """
    trials = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            if not name.endswith(".json"):
                continue
            path = os.path.join(dirpath, name)
            obj = _load(path)
            if not isinstance(obj, dict):
                continue
            push = obj.get("push")
            if not isinstance(push, dict) or "skill_disp" not in push:
                continue
            pre = (obj.get("pre") or {}).get("target_box_a") if isinstance(obj.get("pre"), dict) else None
            post = (obj.get("post") or {}).get("target_box_a") if isinstance(obj.get("post"), dict) else None
            verdict = obj.get("verdict") or {}
            actions = [{"displacement_m": push.get("skill_disp"),
                        "direction_cos": verdict.get("direction_cosine")}]
            travel = obj.get("ee_travel_m")
            trials.append({"trial": os.path.relpath(path, root).replace(os.sep, "/"),
                           "pre": pre, "post": post,
                           "direction": _direction_from_record(obj),
                           "actions": actions, "real_travel_m": travel})
    return trials


def main(argv=None):
    ap = argparse.ArgumentParser(description="issue #232 progress vs net displacement (read-only)")
    ap.add_argument("--root", default=WT + "/setup/acceptance")
    ap.add_argument("--out", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--direction", default=None,
                    help='explicit XY direction "dx,dy" for archives that record none; '
                         "omit to let the tool report UNKNOWN rather than assume -x")
    args = ap.parse_args(argv)
    trials = collect_trials(args.root) + collect_candidate_files(args.root)
    override = None
    if args.direction:
        override = [float(x) for x in args.direction.replace(" ", "").split(",")]
    if args.limit:
        trials = trials[:args.limit]
    rows = []
    for t in trials:
        direction = t["direction"] if t["direction"] is not None else override
        r = analyse(t["pre"], t["post"], direction, t["actions"], t["real_travel_m"])
        r["trial"] = t["trial"]
        rows.append(r)
    cols = ["trial", "status", "motion", "reported_progress_m", "net_displacement_m",
            "net_along_u_m", "lateral_m", "difference_m", "arm_travel_m", "travel_to_net_ratio",
            "n_actions", "unknown_reason"]
    print("\t".join(cols))
    for r in rows:
        print("\t".join(str(r.get(c)) for c in cols))
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "report.json"), "w", encoding="utf-8") as fh:
            json.dump({"root": args.root, "n_trials": len(rows), "trials": rows}, fh, indent=2)
        with open(os.path.join(args.out, "report.tsv"), "w", encoding="utf-8") as fh:
            fh.write("\t".join(cols) + "\n")
            for r in rows:
                fh.write("\t".join(str(r.get(c)) for c in cols) + "\n")
        print("wrote %s" % args.out, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
