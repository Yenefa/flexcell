#!/usr/bin/env python3
"""Compare the deterministic rule planner against the LLM planner on identical observations.

WHY THE COMPARISON RUNS ON THE SAME OBSERVATION: the two planners must be handed exactly what
the agent was handed, or the comparison measures the inputs rather than the planners. Each
archived run has observation_input.json, which is what baseline B actually saw.

TWO DIFFERENT QUESTIONS, kept apart on purpose:
  AGREEMENT - do the two produce the same object->zone mapping and the same order? This needs no
              privileged access and answers "is the LLM doing anything the rules do not".
  ACCURACY  - which one matches the declared goal? That needs the sealed answer, so it is
              attempted and skipped gracefully if the file cannot be read.
A high agreement with low accuracy for both would mean the benchmark is too easy to separate
them, not that the LLM is good.
"""
import glob
import json
import os
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
import rule_planner as RP

SEALED = "/etc/evobot/sealed"
BATCHES = ["/tmp/evobot-batch1", "/tmp/evobot-batch2",
           "/tmp/evobot-batch3", "/tmp/evobot-batch4"]


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def key_of(moves):
    """Reduce a plan to what the evaluator actually checks: object->zone, in order."""
    return [(m.get("object"), m.get("zone")) for m in moves]


def main():
    rows = []
    sealed_ok = os.path.isdir(SEALED) and os.access(SEALED, os.R_OK)
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            obs = read(os.path.join(d, "observation_input.json"))
            if not obs:
                continue
            oid = os.path.basename(d)
            rule_moves, rule_unmoved, note = RP.plan(obs)
            b = read(os.path.join(d, "agent_reply.json")) or {}
            b_moves = (b.get("agent_plan") or {}).get("moves") or \
                      (b.get("agent_plan") or {}).get("stages") or []
            # agent_plan from prepare_baseline_b is already the validated plan object
            ap = b.get("agent_plan")
            if isinstance(ap, dict):
                b_moves = ap.get("moves") or ap.get("stages") or []
            agree = key_of(rule_moves) == key_of(b_moves)
            target = None
            if sealed_ok:
                ans = read(os.path.join(SEALED, oid + ".json")) or {}
                goal = ans.get("expected_goal") or {}
                placement = goal.get("placement") or {}
                order = goal.get("order") or []
                if placement:
                    target = {"placement": placement, "order": order}
            def score(moves):
                if target is None or not moves:
                    return None
                got = {m["object"]: m["zone"] for m in moves}
                places_ok = all(got.get(k) == v for k, v in target["placement"].items())
                order_ok = True
                if target["order"]:
                    seq = [m["object"] for m in moves]
                    order_ok = seq[:len(target["order"])] == target["order"]
                return places_ok and order_ok
            rows.append({
                "id": oid, "agree": agree, "note": note,
                "rule_n": len(rule_moves), "b_n": len(b_moves),
                "rule_ok": score(rule_moves), "b_ok": score(b_moves),
            })

    n = len(rows)
    agree = sum(1 for r in rows if r["agree"])
    print("%-20s %-6s %-6s %-8s %-8s %s" % ("run", "agree", "rule_n", "b_n",
                                            "rule_ok", "b_ok"))
    for r in rows:
        print("%-20s %-6s %-6d %-8d %-8s %s" % (
            r["id"], r["agree"], r["rule_n"], r["b_n"], r["rule_ok"], r["b_ok"]))
    print()
    print("instances compared        :", n)
    print("rule plan == LLM plan     : %d/%d = %.1f%%" % (agree, n, 100.0 * agree / max(1, n)))
    if sealed_ok:
        ro = sum(1 for r in rows if r["rule_ok"])
        bo = sum(1 for r in rows if r["b_ok"])
        print("rule planner correct       : %d/%d" % (ro, n))
        print("LLM planner correct        : %d/%d" % (bo, n))
    else:
        print("(sealed answer not readable - accuracy not scored; agreement only)")
    declined = [r["id"] for r in rows if r["rule_n"] == 0]
    print("rule planner declined      : %d%s" % (len(declined),
                                                  (" " + str(declined)) if declined else ""))
    print()
    print("HOW TO READ THIS: if a fixed parser reproduces the LLM's plan on these templates,")
    print("then on these templates the LLM's measurable contribution is zero, and a claim")
    print("that the agent reasons about the task would be attributing to the agent what a")
    print("regular expression did.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
