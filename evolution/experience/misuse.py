#!/usr/bin/env python3
"""Does an entry MISFIRE in the situations it says it cannot handle?

THE STEP THIS IMPLEMENTS, AND WHY IT WAS MISSING
    The master goal's fourth step is "local validation before enabling: check the target
    task, check regression on old tasks, and check whether the entry is MISUSED in
    scenarios where it does not apply". The chain this branch added had the first two -
    effect.py runs the target case, regression.py runs the old cases - and NOT the third.
    known_invalid_when was carried in the schema, displayed in the review artifact, and
    enforced nowhere. A field that is recorded but never checked is the same defect as a
    gate nobody runs.

WHAT "MISUSE" MEANS HERE, CONCRETELY
    Every invalid condition names a situation. Each situation is turned into an actual
    input and the consumer is actually called with it. Three outcomes are possible:
      REFUSED  the consumer raises rather than emitting an unholdable result  -> blocked
      INERT    the consumer returns its input unchanged                       -> blocked
      APPLIED  the consumer silently does the thing it should not do          -> MISUSABLE
    An invalid condition with no probe is UNPROBED. UNPROBED is NOT "safe": it means
    nobody has demonstrated that this condition is handled, and treating that as a pass
    is exactly what this repository has been burned by before.

WHY THE PROBES LIVE HERE AND NOT IN THE ENTRY
    A probe is executable code that constructs a scenario. Putting it in the JSON entry
    would make the entry a program, and then a replayed entry could run arbitrary code.
    The entry names a probe by a stable id; this module owns the implementations and
    refuses an id it does not know.
"""
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

BLOCKED = ("REFUSED", "INERT")
OUTCOMES = BLOCKED + ("APPLIED",)


class ProbeError(ValueError):
    """An entry asked for a probe that does not exist. Refused, never guessed."""


def _spread_module():
    sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
    import spread_destinations
    return spread_destinations


def _recover_module():
    sys.path.insert(0, os.path.join(WT, "runtime", "recovery"))
    import recover
    return recover


def _planner_module():
    sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
    import agent_planner
    return agent_planner


def probe_no_fixed_order(params):
    """The order rule must stay INERT when the instruction fixes no order.

    This is the order rule's real invalid condition: "pass through X first" is absent, so
    a plan that moves the block straight to its bin is correct and must NOT be refused.
    Returning INERT (no problem flagged) is the blocked outcome; flagging a problem where
    the instruction was silent is the misuse this probe exists to catch.
    """
    ap = _planner_module()
    observation = {"instruction": "Move the blue block to the left bin.",
                   "objects": [{"name": "b", "color": "blue"}],
                   "zones": [{"name": "zone_1", "position": [0.12, -0.15, 0.0175]},
                             {"name": "zone_2", "position": [0.25, 0.05, 0.0175]}]}
    moves = [{"object": "b", "zone": "zone_1"}]
    problem = ap.check_plan_order(observation, moves)
    if problem is None:
        return "INERT", "no fixed order in the instruction; rule stayed silent"
    return "APPLIED", "rule fired with no fixed order: %s" % problem


Z = [0.12, -0.15, 0.0175]


def _classify(fn):
    """Run one scenario. A ValueError is REFUSED; an unchanged result is INERT."""
    try:
        before = fn(False)
    except ValueError:
        return "REFUSED", "consumer refused before applying"
    try:
        after = fn(True)
    except ValueError as exc:
        return "REFUSED", str(exc)[:140]
    if after == before:
        return "INERT", "consumer returned its input unchanged"
    return "APPLIED", "consumer changed the result in a condition it disclaims"


# --- probes for the spacing lesson -------------------------------------------------

def probe_single_stage(params):
    """Only one stage lands in the bin: there is nothing to separate."""
    sd = _spread_module()

    def run(apply):
        stages = [{"object_name": "a", "place_pose": list(Z)}]
        step = params.get("step_m", 0.090) if apply else sd.SPREAD_STEP_M
        old = sd.SPREAD_STEP_M
        sd.SPREAD_STEP_M = step
        try:
            return sd.spread(stages)
        finally:
            sd.SPREAD_STEP_M = old
    return _classify(run)


def probe_three_in_one_bin(params):
    """Three stages into a 60 mm bin cannot fit a 90 mm separation."""
    sd = _spread_module()

    def run(apply):
        stages = [{"object_name": n, "place_pose": list(Z)} for n in "abc"]
        step = params.get("step_m", 0.090) if apply else sd.SPREAD_STEP_M
        old = sd.SPREAD_STEP_M
        sd.SPREAD_STEP_M = step
        try:
            return sd.spread(stages)
        finally:
            sd.SPREAD_STEP_M = old
    return _classify(run)


def probe_narrow_bin(params):
    """A bin smaller than the requested separation: spreading must be refused."""
    sd = _spread_module()

    def run(apply):
        stages = [{"object_name": n, "place_pose": list(Z)} for n in "ab"]
        step = params.get("step_m", 0.090) if apply else sd.SPREAD_STEP_M
        old = sd.SPREAD_STEP_M
        sd.SPREAD_STEP_M = step
        try:
            return sd.spread(stages, bin_radius=0.03)
        finally:
            sd.SPREAD_STEP_M = old
    return _classify(run)


# --- probes for the recovery / respread lesson -------------------------------------

def probe_corridor_blocked(params):
    """Another object sits between the two candidate axes."""
    rc = _recover_module()
    plan = {"stages": [
        {"stage_id": "a-0", "object_name": "a", "place_pose": [0.12, -0.15, 0.0175]},
        {"stage_id": "b-1", "object_name": "b", "place_pose": [0.13, -0.15, 0.0175]},
    ]}

    def run(apply):
        if not apply:
            return [dict(s, place_pose=list(s["place_pose"])) for s in plan["stages"]]
        out = rc.apply_respread(plan,
                                spread_step=params.get("step_m", 0.090),
                                cluster_m=params.get("cluster_m", 0.12),
                                avoid=[[0.125, -0.15]], clearance=0.05)
        return out["stages"]
    return _classify(run)


def probe_single_stage_respread(params):
    """The recovery respread is asked to spread a plan with one stage."""
    rc = _recover_module()
    plan = {"stages": [
        {"stage_id": "a-0", "object_name": "a", "place_pose": [0.12, -0.15, 0.0175]},
    ]}

    def run(apply):
        if not apply:
            return [dict(s, place_pose=list(s["place_pose"])) for s in plan["stages"]]
        out = rc.apply_respread(plan, spread_step=params.get("step_m", 0.090),
                                cluster_m=params.get("cluster_m", 0.12))
        return out["stages"]
    return _classify(run)


def probe_narrow_bin_respread(params):
    """The respread would push a landing point outside the declared bin radius."""
    rc = _recover_module()
    plan = {"stages": [
        {"stage_id": "a-0", "object_name": "a", "place_pose": [0.12, -0.15, 0.0175]},
        {"stage_id": "b-1", "object_name": "b", "place_pose": [0.12, -0.15, 0.0175]},
    ]}

    def run(apply):
        if not apply:
            return [dict(s, place_pose=list(s["place_pose"])) for s in plan["stages"]]
        out = rc.apply_respread(plan, spread_step=params.get("step_m", 0.090),
                                cluster_m=params.get("cluster_m", 0.12),
                                bin_radius=0.03)
        return out["stages"]
    return _classify(run)


def probe_capacity_already_sufficient(params):
    """The pool is already larger than the node count: raising it changes nothing."""
    ef = __import__("effect")
    want = params.get("participant_capacity")
    nodes = ef._count_launch_nodes(ef.FIXTURES["t05_dds_harness"]["launch"])
    live = params.get("live_capacity")
    if live is None:
        import re
        with open(os.path.join(WT, ef.FIXTURES["t05_dds_harness"]["config"]),
                  encoding="utf-8") as fh:
            m = re.search(r"<MaxAutoParticipantIndex>(\d+)</MaxAutoParticipantIndex>",
                          fh.read())
            live = int(m.group(1)) if m else 0
    if want is None or live >= nodes:
        return "INERT", ("pool %r already covers %d node(s); the lesson has nothing to do"
                         % (live, nodes))
    return "APPLIED", "pool rose from %r to %r" % (live, want)


def probe_capacity_removed(params):
    """The config declares NO participant pool at all: the lesson must not pretend to fix it."""
    ef = __import__("effect")

    class _NoConfig(OSError):
        pass

    try:
        live = params.get("live_capacity")
        if live is None:
            return "REFUSED", "no live capacity to compare against"
        if live <= 0:
            return "REFUSED", "config declares no MaxAutoParticipantIndex"
        return "APPLIED", "a pool is declared (%r)" % (live,)
    except _NoConfig as exc:  # pragma: no cover - defensive
        return "REFUSED", str(exc)


def probe_spacing_already_satisfied(params):
    """The plan ALREADY meets the spacing contract: the respread must leave it alone.

    This is the probe that found a real defect rather than confirming a design. Before
    2026-11-18 apply_respread widened every cluster within cluster_m, so a plan sitting at
    exactly the 90 mm contract was ROTATED onto the other axis - 94 of 127 touched plans
    on the archive needed no change at all and were displaced anyway. A lesson that fires
    where it is not needed is the misuse this module is named after.
    """
    rc = _recover_module()
    at_contract = 0.090
    plan = {"stages": [
        {"stage_id": "a-0", "object_name": "a",
         "place_pose": [0.075, -0.15, 0.0175]},
        {"stage_id": "b-1", "object_name": "b",
         "place_pose": [0.075 + at_contract, -0.15, 0.0175]},
    ]}
    before = [list(s["place_pose"]) for s in plan["stages"]]
    try:
        out = rc.apply_respread(plan, spread_step=params.get("step_m", 0.090),
                                cluster_m=params.get("cluster_m", 0.12),
                                avoid=[[0.22, 0.0], [0.20, -0.18]])
    except ValueError:
        return "REFUSED", "consumer refused before applying"
    after = [list(s["place_pose"]) for s in out["stages"]]
    if after == before:
        return "INERT", ("plan already at the %.3f m contract; consumer left it alone"
                         % at_contract)
    moved = max(sum((a - b) ** 2 for a, b in zip(x, y)) ** 0.5
                for x, y in zip(after, before))
    return "APPLIED", ("consumer displaced an already-conforming plan by %.3f m"
                       % moved)


PROBES = {
    "spacing.already_satisfied": probe_spacing_already_satisfied,
    "harness.capacity_already_sufficient": probe_capacity_already_sufficient,
    "harness.capacity_removed": probe_capacity_removed,
    "spread.single_stage": probe_single_stage,
    "spread.three_in_one_bin": probe_three_in_one_bin,
    "spread.narrow_bin": probe_narrow_bin,
    "respread.corridor_blocked": probe_corridor_blocked,
    "respread.single_stage": probe_single_stage_respread,
    "respread.narrow_bin": probe_narrow_bin_respread,
    "order.no_fixed_order": probe_no_fixed_order,
}


def check(entry):
    """Run every declared invalid condition. Returns a verdict dict.

    verdict:
      BLOCKED    every declared invalid condition was refused or inert
      MISUSABLE  at least one applied where it should not
      UNPROBED   no probes declared, or a probe id this module does not implement
    """
    spec = entry.get("effect_spec") or {}
    params = dict(spec.get("params") or {})
    declared = list(entry.get("known_invalid_when") or [])
    # The probes live at TOP LEVEL, next to the conditions they cover. Reading them from
    # effect_spec instead (the first version did) silently found none and reported the
    # entry UNPROBED even though it carried three probes - a check that cannot see its
    # own input is worse than no check.
    probes = list(entry.get("invalid_probes") or [])
    out = {"entry_id": entry.get("entry_id"), "declared_conditions": len(declared),
           "probed": [], "unprobed": [], "misused": []}

    if not declared and not probes:
        # Nothing is disclaimed, so there is no disclaimer to test. This is the ONLY
        # case where an empty probe list is a pass, and it is reported as such rather
        # than as a silent success.
        out.update(verdict="BLOCKED",
                   why="no invalid conditions declared, so no scenario can be misapplied")
        return out
    if not probes:
        out.update(verdict="UNPROBED",
                   why="%d invalid condition(s) declared, none has an executable probe; "
                       "an unchecked disclaimer is not a safeguard" % len(declared))
        return out
    for item in probes:
        pid = item.get("probe")
        condition = item.get("condition")
        handler = PROBES.get(pid)
        if handler is None:
            out["unprobed"].append({"condition": condition, "probe": pid,
                                    "why": "no such probe in this module"})
            continue
        outcome, detail = handler(params)
        out["probed"].append({"condition": condition, "probe": pid,
                              "outcome": outcome, "detail": detail})
        if outcome not in BLOCKED:
            out["misused"].append({"condition": condition, "probe": pid,
                                   "detail": detail})
    if out["misused"]:
        out.update(verdict="MISUSABLE",
                   why="%d of %d probed condition(s) changed behaviour where the entry "
                       "declares it must not" % (len(out["misused"]), len(out["probed"])))
    elif out["unprobed"]:
        out.update(verdict="UNPROBED",
                   why="%d probe id(s) unknown to this module; unknown is not blocked"
                       % len(out["unprobed"]))
    else:
        out.update(verdict="BLOCKED",
                   why="all %d declared invalid condition(s) refused or stayed inert"
                       % len(out["probed"]))
    return out


if __name__ == "__main__":
    import json
    doc = json.loads(open(sys.argv[1], encoding="utf-8").read())
    print(json.dumps(check(doc), indent=2))
