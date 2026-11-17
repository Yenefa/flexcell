#!/usr/bin/env python3
"""Execute an entry's effect against REAL archived inputs and measure whether it changed anything.

THE MEASUREMENT THIS REPLACES
    Two independent B/C experiments compared plans and found them byte-identical. The
    conclusion available at the time was "experience had no effect", which is a null
    result. It took a separate audit to discover the mechanism: the lesson described a
    landing coordinate and the planner never emits one. The lesson was true, the delivery
    address was wrong, and nobody could see that from the experiment's output.

    So an entry does not get to assert its effect. Its effect_spec is EXECUTED here:
    the same archived input is put through the consumer twice, once as the code stands
    and once with the entry's change applied, and the two outputs are compared. The
    verdict is computed from those outputs, never written by hand.

WHAT "NO_CHANGE" MEANS, AND WHY IT IS NOT A FAILURE OF THE ENTRY
    NO_CHANGE says this consumer's output did not move on this input. For a spacing
    parameter on a plan whose two landings are already far apart, NO_CHANGE is the
    correct answer and the honest one. The entry is then still allowed to be ACTIVE, but
    the ledger records that applying it changed nothing here, so a later reader cannot
    mistake "retrieved" for "used".

WHAT IT CANNOT MEASURE
    Prompt-level consumers (the planner) need a model call. Measured offline, a prompt
    change produces the same prompt-in, same-plan-out, which would be a fabricated
    null. consumers.CONSUMERS marks those measurable_offline=False and this module
    returns UNMEASURED instead of inventing a result.
"""
import contextlib
import hashlib
import json
import math
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import consumers  # noqa: E402

# Fixtures are ARCHIVED RUNS, not synthetic inputs: an effect measured on an input that
# was never executed proves nothing about this robot.
FIXTURES = {
    "t13_two_boxes_one_bin": {
        "plan": "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/plan.json",
        "evidence": "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/"
                    "failure_evidence.json",
        "what": "the real T13 run whose 9.65 mm landing error consumed a 6 mm margin",
    },
    "ho_partial_commit": {
        "plan": "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/plan.json",
        "evidence": "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/"
                    "failure_evidence.json",
        "what": "the same run read as a partial commit (stage a committed, stage b did not)",
        "committed_stage_ids": ["target_box_a-0"],
    },
    "ho_uncommitted_planning": {
        "plan": "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/plan.json",
        "evidence": "setup/acceptance/evobot_recover_n6_20261111/runs/HO-90899d657e68/"
                    "failure_evidence.json",
        "what": "the same measured failure read with NO committed stage, which is the "
                "state the driver saw before it learned that a failed PLACE can still "
                "move the world",
        "committed_stage_ids": [],
    },
    # THE FIRST DEVELOPMENT-SPLIT FIXTURE in this package. Every other fixture reads a
    # held-out instance, because the T12/T13 families exist only there. This one does not:
    # evobot_t05_* runs T05 train seeds (s1000-s1005 are benchmark/tasks/train), which is
    # why the DDS lesson can be learned from development evidence and still be real.
    "t05_dds_harness": {
        "before_batch": "setup/acceptance/evobot_t05_n6_20261111",
        "after_batch": "setup/acceptance/evobot_t05_n6_clean_20261111",
        "config": "config/cyclonedds.xml",
        "launch": "src/flexcell/flexcell_skills/launch/trusted_sim.launch.py",
        "what": "the T05 n=6 batch where 2 of 6 runs never dispatched because CyloneDDS "
                "could not allocate a participant, and the next batch after the pool was "
                "raised where 6 of 6 dispatched",
    },
}

OPERATORS = ("spread_step", "respread_apply", "recovery_action",
             "harness_capacity", "none")


def _digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def _load(rel):
    with open(os.path.join(WT, rel), encoding="utf-8") as fh:
        return json.load(fh)


def _spread_module():
    sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
    import spread_destinations
    return spread_destinations


def _recover_module():
    sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
    import recover
    return recover


@contextlib.contextmanager
def _patched(module, name, value):
    """Temporarily set a module-level constant, and put it back even on an exception.

    The spread policy reads SPREAD_STEP_M at call time, so an entry that changes the
    step is only measurable by changing that constant. Restoring it in finally is what
    keeps a measurement from leaking into the next one.
    """
    old = getattr(module, name)
    setattr(module, name, value)
    try:
        yield
    finally:
        setattr(module, name, old)


def _min_separation(stages):
    pts = [(float(s["place_pose"][0]), float(s["place_pose"][1])) for s in stages]
    if len(pts) < 2:
        return None
    return min(math.hypot(a[0] - b[0], a[1] - b[1])
               for i, a in enumerate(pts) for b in pts[i + 1:])


def _min_clearance_to(stages, avoid):
    if not avoid:
        return None
    return min(math.hypot(float(s["place_pose"][0]) - float(a[0]),
                          float(s["place_pose"][1]) - float(a[1]))
               for s in stages for a in avoid)


def _run_spread(plan, params):
    """Compare the CURRENT step against the step this entry proposes.

    The baseline is what the code does today, so "applied" is a counterfactual: what the
    output WOULD be if the entry were adopted. Writing it the other way round (patch to
    the current value and compare with itself) would manufacture NO_CHANGE on every
    entry, which is the fabricated null this module exists to avoid.
    """
    sd = _spread_module()
    stages = plan["stages"]
    avoid = [o["position"][:2] for o in plan.get("initial_objects", [])
             if o.get("position")]
    proposed = params.get("step_m")
    if proposed is None:
        return sd.spread(stages, avoid=avoid), sd.spread(stages, avoid=avoid), {
            "note": "no step_m in effect_spec"}
    baseline_step = float(params.get("baseline_step_m", sd.SPREAD_STEP_M))
    with _patched(sd, "SPREAD_STEP_M", baseline_step):
        baseline = sd.spread(stages, avoid=avoid)
    with _patched(sd, "SPREAD_STEP_M", float(proposed)):
        applied = sd.spread(stages, avoid=avoid)
    return baseline, applied, {"baseline_step_m": baseline_step,
                               "step_m": float(proposed)}


def _run_respread(plan, params):
    """The EXECUTOR-side respread, which clusters by distance rather than exact pose.

    This operator exists because the two consumers of a spacing lesson are not the same
    code. planner-side spread() groups stages by EXACT equal place_pose; the plan builder
    has already offset same-bin stages by 56 mm, so those poses are never equal and
    spread() changes nothing. The executor-side apply_respread() clusters by distance,
    which is the grouping the plan actually has. Measuring the lesson on the planner-side
    consumer therefore reports NO_CHANGE on a plan the executor-side consumer would fix -
    the delivery address matters one layer deeper than the previous audit noticed.
    """
    rc = _recover_module()
    baseline = [dict(s, place_pose=list(s["place_pose"])) for s in plan["stages"]]
    step = float(params.get("step_m", 0.090))
    cluster = float(params.get("cluster_m", 0.12))
    avoid = [o["position"][:2] for o in plan.get("initial_objects", [])
             if o.get("position")]
    applied = rc.apply_respread(plan, spread_step=step, cluster_m=cluster,
                                avoid=avoid)["stages"]
    return baseline, applied, {"step_m": step, "cluster_m": cluster,
                               "avoid": avoid}


def _run_recovery(plan, params, evidence):
    rc = _recover_module()
    baseline = rc.decide(evidence)
    target_class = params.get("failure_class")
    new_action = params.get("action")
    if not target_class or not new_action:
        return baseline, baseline, {"note": "effect_spec needs failure_class and action"}
    table = dict(rc.ACTION_TABLE)
    table[target_class] = new_action
    with _patched(rc, "ACTION_TABLE", table):
        applied = rc.decide(evidence)
    return baseline, applied, {"failure_class": target_class, "action": new_action}


def _count_harness_failures(batch_dir):
    """Count rows whose layer is HARNESS in an archived batch's summary.txt.

    HARNESS is a LAYER, not an error code: those runs never dispatched a task at all, so
    they carry no task.out and no error_code. Counting them by error code would report
    zero and make the DDS bug invisible - which is exactly how it stayed undiagnosed for
    two rounds while it was being blamed on "Gazebo instability".
    """
    import glob as _glob
    total, harness = 0, 0
    for path in _glob.glob(os.path.join(WT, batch_dir, "summary.txt")):
        for line in open(path, encoding="utf-8", errors="replace"):
            parts = line.split()
            if len(parts) < 3 or not parts[0].startswith("s"):
                continue
            total += 1
            if parts[2] == "HARNESS":
                harness += 1
    return harness, total


def _count_launch_nodes(rel):
    """Nodes one launch file starts, by counting Node( constructions in the source."""
    import re
    with open(os.path.join(WT, rel), encoding="utf-8") as fh:
        return len(re.findall(r"\bNode\(", fh.read()))


def _run_harness(params):
    """Measure a harness lesson as an ARCHIVED BEFORE/AFTER pair, plus the current contract.

    Two measurements, because either alone can mislead:
      1. the archived pair - the same seeds, same launch, one batch before the pool was
         raised and one after. This is the evidence the lesson was learned from, and it is
         DEVELOPMENT split (T05 train seeds), so it is not circular.
      2. the live contract - does the config's pool still exceed the number of nodes the
         launch starts? A past fix proves nothing about today's tree; a later edit could
         lower the pool and silently reinstate the bug.
    """
    spec = FIXTURES["t05_dds_harness"]
    before_h, before_n = _count_harness_failures(spec["before_batch"])
    after_h, after_n = _count_harness_failures(spec["after_batch"])
    nodes = _count_launch_nodes(spec["launch"])
    capacity = params.get("participant_capacity")
    with open(os.path.join(WT, spec["config"]), encoding="utf-8") as fh:
        text = fh.read()
    import re
    m = re.search(r"<MaxAutoParticipantIndex>(\d+)</MaxAutoParticipantIndex>", text)
    live_capacity = int(m.group(1)) if m else 0
    baseline = {"harness_failures": before_h, "runs": before_n,
                "capacity": params.get("baseline_capacity", 0),
                "capacity_covers_nodes": False}
    applied = {"harness_failures": after_h, "runs": after_n,
               "capacity": capacity if capacity is not None else live_capacity,
               "capacity_covers_nodes": (capacity if capacity is not None
                                         else live_capacity) >= nodes}
    return baseline, applied, {
        "before_batch": spec["before_batch"], "after_batch": spec["after_batch"],
        "before_harness_failures": before_h, "before_runs": before_n,
        "after_harness_failures": after_h, "after_runs": after_n,
        "launch_nodes": nodes, "live_capacity": live_capacity,
    }


def probe(entry):
    """Run one entry's effect_spec. Returns a verdict dict; never raises for a bad spec."""
    spec = entry.get("effect_spec") or {}
    fixture = spec.get("fixture")
    operator = spec.get("operator", "none")
    consumer = entry.get("consumer")
    out = {"entry_id": entry.get("entry_id"), "consumer": consumer,
           "fixture": fixture, "operator": operator}

    if consumer not in consumers.CONSUMERS:
        out.update(verdict="UNMEASURED", why="unknown consumer %r" % (consumer,))
        return out
    if not consumers.CONSUMERS[consumer]["measurable_offline"]:
        out.update(verdict="UNMEASURED",
                   why="%r delivers at the %s layer; a model call is required and this "
                       "prober does not make one" % (consumer,
                                                     consumers.CONSUMERS[consumer]["delivery"]))
        return out
    if fixture not in FIXTURES:
        out.update(verdict="UNMEASURED", why="unknown fixture %r" % (fixture,))
        return out
    if operator not in OPERATORS or operator == "none":
        out.update(verdict="UNMEASURED", why="no runnable operator in effect_spec")
        return out

    params = spec.get("params") or {}
    # A harness entry's fixture has NO plan: its evidence is an archived batch PAIR and a
    # config file. Loading FIXTURES[fixture]["plan"] first would KeyError on exactly the
    # fixture that proves harness delivery is measurable at all.
    if operator == "harness_capacity":
        try:
            baseline, applied, detail = _run_harness(params)
        except (ValueError, KeyError, OSError) as exc:
            out.update(verdict="REFUSED", why="%s: %s" % (type(exc).__name__, exc))
            return out
        out["detail"] = detail
        out["baseline_sha"] = _digest(baseline)[:16]
        out["applied_sha"] = _digest(applied)[:16]
        out["changed"] = out["baseline_sha"] != out["applied_sha"]
        out["verdict"] = "CHANGED" if out["changed"] else "NO_CHANGE"
        out["baseline_harness_failures"] = detail["before_harness_failures"]
        out["applied_harness_failures"] = detail["after_harness_failures"]
        out["launch_nodes"] = detail["launch_nodes"]
        out["live_capacity"] = detail["live_capacity"]
        expect = spec.get("expect") or {}
        out["expectations"] = _check_expectations(expect, out)
        out["expectations_met"] = (all(out["expectations"].values())
                                   if out["expectations"] else None)
        return out

    plan = _load(FIXTURES[fixture]["plan"])
    try:
        if operator == "spread_step":
            baseline, applied, detail = _run_spread(plan, params)
        elif operator == "respread_apply":
            baseline, applied, detail = _run_respread(plan, params)
        elif operator == "recovery_action":
            evidence = _load(FIXTURES[fixture]["evidence"])
            if fixture == "ho_partial_commit":
                evidence = dict(evidence, completed_stage_ids=["target_box_a-0"])
            baseline, applied, detail = _run_recovery(plan, params, evidence)
        else:  # pragma: no cover - guarded above
            raise ValueError("unreachable operator")
    except (ValueError, KeyError, OSError) as exc:
        # A consumer that REFUSES is a real outcome, not an error: the spread policy is
        # designed to refuse rather than emit an unholdable plan.
        out.update(verdict="REFUSED", why="%s: %s" % (type(exc).__name__, exc))
        return out

    out["detail"] = detail
    out["baseline_sha"] = _digest(baseline)[:16]
    out["applied_sha"] = _digest(applied)[:16]
    changed = out["baseline_sha"] != out["applied_sha"]
    out["changed"] = changed
    out["verdict"] = "CHANGED" if changed else "NO_CHANGE"

    # Numeric read-out, so a reader can see HOW it changed and not only that it did.
    if operator in ("spread_step", "respread_apply"):
        out["baseline_min_separation_m"] = _min_separation(baseline)
        out["applied_min_separation_m"] = _min_separation(applied)
        avoid = [o["position"][:2] for o in plan.get("initial_objects", [])
                 if o.get("position")]
        out["baseline_min_clearance_m"] = _min_clearance_to(baseline, avoid)
        out["applied_min_clearance_m"] = _min_clearance_to(applied, avoid)
    else:
        out["baseline_action"] = baseline.get("action")
        out["applied_action"] = applied.get("action")

    expect = spec.get("expect") or {}
    out["expectations"] = _check_expectations(expect, out)
    out["expectations_met"] = all(v for v in out["expectations"].values()) if         out["expectations"] else None
    return out


def _check_expectations(expect, out):
    """Each declared expectation is checked against a MEASURED number, never prose."""
    got = {}
    for key, want in (expect or {}).items():
        if key.endswith("_gte"):
            field = key[:-4]
            value = out.get(field)
            got[key] = value is not None and float(value) >= float(want)
        elif key.endswith("_lte"):
            field = key[:-4]
            value = out.get(field)
            got[key] = value is not None and float(value) <= float(want)
        elif key == "changed":
            got[key] = bool(out.get("changed")) == bool(want)
        else:
            got[key] = False
    return got


if __name__ == "__main__":
    doc = json.loads(open(sys.argv[1], encoding="utf-8").read())
    print(json.dumps(probe(doc), indent=2))
