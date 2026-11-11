#!/usr/bin/env python3
"""Attribute EVERY failed first attempt across every validated batch to a layer.

THE QUESTION: Level 7 Transfer has never been observed - lessons do not change plans. Two very
different explanations fit that observation, and they imply opposite next steps:
  (a) the delivery is broken: lessons exist that would help, but reach the wrong consumer;
  (b) there is nothing to deliver: the planner commits no errors, so no planner-level lesson
      can improve it, and the capability gap lies below the planner.
I have argued (a) before. This measures it.

A failure is PLANNER-attributable only if the plan itself was wrong: an object omitted, a wrong
destination, a violated declared constraint, an unparseable reply. Everything else - a skill that
stalled, a release that did not confirm, a run that stopped short - is an EXECUTION failure and
no amount of planning experience can prevent it.
"""
import glob
import json
import os
import sys

BATCHES = ["/tmp/evobot-batch1", "/tmp/evobot-batch2",
           "/tmp/evobot-batch3", "/tmp/evobot-batch4"]
PLANNER_SIGNS = ("plan", "declared", "zone_1", "zone_2", "object", "parse", "json")


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


def outcome(d):
    p = os.path.join(d, "task.out")
    if not os.path.exists(p):
        return None
    t = open(p, encoding="utf-8", errors="replace").read()
    i = t.rfind("RESULT ")
    if i < 0:
        return None
    try:
        return json.loads(t[i + 7:]).get("outcome")
    except Exception:
        return None


def attribute(d):
    """Return (layer, why). Layer is PLANNER or EXECUTION or UNKNOWN."""
    ev = read(os.path.join(d, "failure_evidence.json"))
    dec = read(os.path.join(d, "recovery_decision.json"))
    dec = dec.get("decision") or dec
    # Build the searchable detail carefully: native_fsm_trace is a LIST, and str() on a list
    # yields "['']", which is never empty. That made the emptiness test useless and every
    # evidence-less run classify as EXECUTION instead of UNKNOWN - a vacuous-zero shape.
    parts = [ev.get("detail"), ev.get("native_detail"), dec.get("measured_reason"),
             dec.get("why")]
    trace = ev.get("native_fsm_trace")
    if isinstance(trace, (list, tuple)):
        parts.extend(trace)
    elif trace:
        parts.append(trace)
    detail = " ".join(str(x) for x in parts if x).strip().lower()

    # A plan that was produced is evidence the planner ran; a planner failure names the plan
    plan_file = os.path.join(d, "plan.json")
    plan_exists = os.path.exists(plan_file)

    if not plan_exists:
        return "PLANNER", "no plan was produced at all"
    for sign in ("plan must declare", "unparseable", "no json in reply",
                 "unknown zone", "must declare every observed object"):
        if sign in detail:
            return "PLANNER", "plan defect: " + sign
    if detail in ("", "none"):
        return "UNKNOWN", "no failure evidence recorded"
    return "EXECUTION", (dec.get("failure_class") or "unclassified")


def main():
    print("%-10s %-20s %-10s %-16s %s" % ("batch", "run", "task", "layer", "why"))
    counts = {"PLANNER": 0, "EXECUTION": 0, "UNKNOWN": 0, "ok": 0}
    per_batch = {}
    for base in BATCHES:
        if not os.path.isdir(base):
            continue
        name = os.path.basename(base)
        per_batch[name] = {"PLANNER": 0, "EXECUTION": 0, "UNKNOWN": 0, "ok": 0}
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            v1 = read(os.path.join(d, "verdict_after1.json"))
            oc = outcome(d)
            if v1.get("passed") and oc == 0:
                counts["ok"] += 1
                per_batch[name]["ok"] += 1
                continue
            if v1.get("passed"):
                # the world was fine; the task's own report was wrong (false failure)
                layer, why = "EXECUTION", "task reported failure while the world was correct"
            else:
                layer, why = attribute(d)
            counts[layer] += 1
            per_batch[name][layer] += 1
            print("%-10s %-20s %-10s %-16s %s" % (
                name.replace("evobot-", ""), os.path.basename(d),
                "ok" if oc == 0 else "fail", layer, str(why)[:52]))
    print()
    total = sum(counts.values())
    print("runs considered          :", total)
    print("passed cleanly           :", counts["ok"])
    print("PLANNER-attributable     :", counts["PLANNER"])
    print("EXECUTION-attributable   :", counts["EXECUTION"])
    print("unattributed             :", counts["UNKNOWN"])
    print()
    for b, c in per_batch.items():
        print("  %-18s ok=%-3d planner=%-2d execution=%-2d unknown=%d" % (
            b.replace("evobot-", ""), c["ok"], c["PLANNER"], c["EXECUTION"],
            c["UNKNOWN"]))
    print()
    if counts["PLANNER"] == 0:
        print("CONCLUSION: no failure is attributable to planning. Level 7 Transfer is")
        print("UNOBSERVABLE here because there is nothing for a planning lesson to fix -")
        print("the gap sits below the planner, in execution. That is a different claim from")
        print("\"lesson delivery is broken\", and it changes what would have to change.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
