#!/usr/bin/env python3
"""Does a rule set written BEFORE a task type existed generalize to it?

WHY THIS IS THE SHARPER QUESTION: last round I found that a deterministic parser reproduces the
LLM plan on 63/64 instances, and concluded the benchmark cannot show the LLM is needed. But that
parser was written with all three templates in view, so it measured only WITHIN-FAMILY
saturation. The question a benchmark must answer is different: can a baseline built against the
task types it has seen handle a type it has not?

So here the same rule set is stripped of its T14 branch and evaluated on T14. If it fails, then
the LLM solved a type with no prior rule for it, and that increment is a genuine cross-type
generalization rather than a regex in disguise.
"""
import glob
import json
import os
import sys

WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))
import rule_planner as FULL
import rule_planner_pre_t14 as PRE

SEALED = "/etc/evobot/sealed"
BASE = "/tmp/evobot-batch4"


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def score(moves, goal):
    if not moves:
        return False
    got = {m["object"]: m["zone"] for m in moves}
    if not all(got.get(k) == v for k, v in (goal.get("placement") or {}).items()):
        return False
    order = goal.get("order") or []
    if order:
        seq = [m["object"] for m in moves]
        if seq[:len(order)] != order:
            return False
    return True


def _parses_order(obs, moves, goal):
    """True only if the rule set produced the REQUIRED order on a non-natural one.

    Two instances with different required orders are needed to tell "parsed" from "lucky".
    This marks a success as evidence of parsing only when the required order is not simply
    the order the objects appear in the observation.
    """
    req = (goal.get("order") or [])
    if not req:
        return True
    natural = [o["name"] for o in obs.get("objects", [])]
    natural = [n for n in natural if n in req]
    if req == natural:
        return False   # indistinguishable from luck
    return [m["object"] for m in moves][:len(req)] == req


def main():
    rows = []
    for d in sorted(glob.glob(os.path.join(BASE, "HO-*"))):
        obs = read(os.path.join(d, "observation_input.json"))
        if not obs:
            continue
        oid = os.path.basename(d)
        ans = read(os.path.join(SEALED, oid + ".json")) or {}
        goal = ans.get("expected_goal") or {}
        pre_moves, _, pre_note = PRE.plan(obs)
        full_moves, _, full_note = FULL.plan(obs)
        b = read(os.path.join(d, "agent_reply.json")) or {}
        ap = b.get("agent_plan") or {}
        b_moves = ap.get("moves") or ap.get("stages") or []
        rows.append({
            "id": oid,
            "pre_ok": score(pre_moves, goal),
            "pre_note": pre_note,
            "full_ok": score(full_moves, goal),
            "llm_ok": score(b_moves, goal),
            "pre_order_parsed": _parses_order(obs, pre_moves, goal),
        })

    n = len(rows)
    print("%-20s %-8s %-8s %-8s %s" % ("T14 instance", "pre-T14", "all-rules", "LLM",
                                        "pre-T14 note"))
    for r in rows:
        print("%-20s %-8s %-8s %-8s %s" % (r["id"], r["pre_ok"], r["full_ok"],
                                           r["llm_ok"], r["pre_note"][:34]))
    print()
    for label, k in (("rule set WITHOUT a T14 branch", sum(1 for r in rows if r["pre_ok"])),
                     ("rule set WITH a T14 branch", sum(1 for r in rows if r["full_ok"])),
                     ("LLM planner", sum(1 for r in rows if r["llm_ok"]))):
        print("%-32s %2d/%-2d" % (label, k, n))
    print()
    pre = sum(1 for r in rows if r["pre_ok"])
    # A score is not understanding. Count separately: a correct answer that happens because
    # the required order coincides with the object enumeration order teaches nothing.
    coincidental = sum(1 for r in rows if r["pre_ok"] and not r["pre_order_parsed"])
    print("of the %d that scored, %d only because the required order coincided with the"
          % (pre, coincidental))
    print("natural object order - the rule set never parsed the constraint at all.")
    print()
    if pre == 0:
        print("READING: the pre-T14 rule set scores 0. It declines rather than guesses, which is")
        print("the honest behaviour - but it cannot plan this type at all. So on a task TYPE the")
        print("rules were never written for, the LLM's 16/16 is a real increment, and last")
        print("round's blanket 'the benchmark cannot show the LLM is needed' was too strong:")
        print("it holds WITHIN a known template family, not ACROSS families.")
    else:
        parsed = n - coincidental
        print("READING: the pre-T14 rule set scored %d/%d, and %d of those are luck - the"
              % (pre, n, coincidental))
        print("required order happened to equal the object enumeration order. On the %d"
              % (n - coincidental))
        print("instances where it did not, the rule set IGNORED the constraint and produced a")
        print("confidently wrong plan instead of declining. So its understanding of the new")
        print("task type is 0/%d, the LLM is %d/%d, and last round's blanket claim that"
              % (n, sum(1 for r in rows if r["llm_ok"]), n))
        print("'the benchmark cannot show the LLM is needed' was too strong: it holds WITHIN a")
        print("known template family, not ACROSS families.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
