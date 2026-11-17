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
    # The only fixture that is a TASK SPEC rather than an archived run: a planner entry's
    # delivery is rendered against an observation, and the observation comes from a public
    # task file. This one is held-out, which is fine for a delivery check - it proves the
    # text reaches the prompt renderer, not that the plan improves.
    "t14_ordered_pair": {
        "task": "benchmark/held_out/unseen_public/HO-90899d657e68.json",
        "what": "a public task spec, used to build the observation a planner entry renders into",
    },
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
             "harness_capacity", "delivery", "plan_order", "none")


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
    # The measurable_offline flag says the consumer's EFFECT cannot be measured without a
    # model. It does not say DELIVERY is unmeasurable, and treating the two as one meant a
    # planner entry could never be checked at all - even for the one thing that IS
    # deterministic about it, namely whether its text reaches the prompt renderer.
    #
    # Two operators now do measure something real about the planner without a model call:
    #   delivery    whether the entry's text reaches the prompt renderer (an ENVELOPE fact)
    #   plan_order  whether the planner's own validator refuses a plan that reverses an
    #               order the instruction fixed (a RULE, not a judgement - the evaluator
    #               still owns whether a plan is correct)
    # Neither claims the plan IMPROVED. That claim still needs a model, and the verdict for
    # it stays UNMEASURED.
    MODEL_FREE = ("delivery", "plan_order")
    if (not consumers.CONSUMERS[consumer]["measurable_offline"]
            and operator not in MODEL_FREE):
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
    # DELIVERY, for the prompt-level consumer. This measures whether the entry's text
    # reaches the consumer's input - deterministically, no model call - and deliberately
    # does NOT claim the plan changed. "Delivered" and "effective" are different, and
    # conflating them is how a delivered-but-inert lesson gets recorded as evidence about
    # the lesson rather than about the envelope.
    # PLAN_ORDER, for the planner consumer. Unlike delivery this measures an EFFECT: the
    # planner's own validator runs over archived (instruction, plan) pairs and the operator
    # counts plans it now refuses. It is deterministic and model-free because the check is a
    # rule, not a judgement - the evaluator still owns whether a plan is CORRECT.
    if operator == "plan_order":
        import glob as _glob
        import re as _re
        sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
        import agent_planner
        rows = []
        for path in _glob.glob(os.path.join(WT, "setup", "acceptance", "**",
                                            "agent_reply.json"), recursive=True):
            run = os.path.dirname(path)
            obs_path = os.path.join(run, "observation_input.json")
            if not os.path.exists(obs_path):
                continue
            try:
                reply = json.load(open(path, encoding="utf-8"))
                observation = json.load(open(obs_path, encoding="utf-8"))
            except (OSError, ValueError):
                continue
            text = str(observation.get("instruction") or "")
            m = _re.search(r"the (\w+) block must be put there FIRST", text, _re.I)
            if not m:
                continue
            colours = {str(o.get("color", "")).lower(): o.get("name")
                       for o in observation.get("objects") or []}
            required = colours.get(m.group(1).lower())
            moves = (reply.get("agent_plan") or {}).get("moves") or []
            first = moves[0].get("object") if moves else None
            compliant = (required == first)
            flagged = agent_planner.check_plan_order(observation, moves) is not None
            rows.append({"run": os.path.relpath(path, WT)[:80], "compliant": compliant,
                         "flagged": flagged})
        # THE ARCHIVE'S ONLY GENUINE REORDERING IS A DIFFERENT SHAPE. Every plan the agent
        # wrote for its OWN task obeyed the order. The one reversal is the wrongplan probe,
        # where a plan authored for HO-128c6a was executed against HO-0dcde4d - so the
        # violation is "this plan, checked against THAT instruction". Scanning only
        # same-run pairs therefore reports zero violations and the check looks untested.
        foreign = os.path.join(WT, "setup", "acceptance", "evobot_wrongplan_probe_20261111",
                               "run_foreign_plan")
        foreign_caught = None
        if os.path.isdir(foreign):
            try:
                f_plan = json.load(open(os.path.join(foreign, "plan.json"),
                                        encoding="utf-8"))
                f_verdict = json.load(open(os.path.join(foreign, "verdict.json"),
                                           encoding="utf-8"))
                host = os.path.join(WT, "setup", "acceptance",
                                    "evobot_crosstype_20261111", "runs_T14_ordered_pair",
                                    str(f_verdict.get("task_id")),
                                    "observation_input.json")
                if os.path.exists(host):
                    host_obs = json.load(open(host, encoding="utf-8"))
                    f_moves = [{"object": s.get("object_name"), "zone": s.get("zone_name")}
                               for s in f_plan.get("stages") or []]
                    foreign_caught = (agent_planner.check_plan_order(host_obs, f_moves)
                                      is not None)
            except (OSError, ValueError):
                foreign_caught = None
        caught = sum(1 for r in rows if not r["compliant"] and r["flagged"])
        false_pos = sum(1 for r in rows if r["compliant"] and r["flagged"])
        viol = sum(1 for r in rows if not r["compliant"])
        out["detail"] = {"order_fixing_replies": len(rows),
                         "violations": viol, "caught": caught,
                         "false_positives": false_pos,
                         "compliant_passed_through": len(rows) - viol - false_pos,
                         "archived_foreign_reordering_caught": foreign_caught,
                         "archived_foreign_reordering": (
                             "evobot_wrongplan_probe_20261111/run_foreign_plan")}
        positive = caught > 0 or bool(foreign_caught)
        out["changed"] = positive or false_pos > 0
        out["verdict"] = ("IMPROVED" if positive and not false_pos
                          else ("BROKEN" if false_pos else "NO_CHANGE"))
        out["why"] = ("%d same-run plan(s) whose instruction fixes an order (%d reversed, "
                      "%d caught, %d wrongly refused); the archive's one genuine reordering "
                      "is the foreign plan, caught=%s"
                      % (len(rows), viol, caught, false_pos, foreign_caught))
        expect = spec.get("expect") or {}
        got = {}
        for key, want in expect.items():
            if key == "catches_violations":
                got[key] = positive == bool(want)
            elif key == "no_false_positives":
                got[key] = (false_pos == 0) == bool(want)
            else:
                got[key] = False
        out["expectations"] = got
        out["expectations_met"] = all(got.values()) if got else None
        return out

    if operator == "delivery":
        import delivery as _delivery
        import public_observation as _po
        sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
        task = _load(FIXTURES[fixture]["task"])
        observation = _po.build_observation(task)
        result = _delivery.deliver(entry, observation)
        out["detail"] = result
        out["delivered"] = result.get("delivered", result.get("verdict") == "DELIVERED")
        out["delivery_verdict"] = result.get("verdict")
        out["text_source"] = result.get("text_source")
        # A delivered prompt is still UNMEASURED as an EFFECT: no model was asked, so
        # nothing here says the plan improved.
        out["verdict"] = "UNMEASURED"
        out["why"] = ("delivery %s (%s); the plan-level effect needs a model call and is "
                      "not measured" % (result.get("verdict"), result.get("why")))
        expect = spec.get("expect") or {}
        got = {}
        for key, want in expect.items():
            if key == "delivered":
                got[key] = bool(out["delivered"]) == bool(want)
            else:
                got[key] = False
        out["expectations"] = got
        out["expectations_met"] = all(got.values()) if got else None
        return out

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
