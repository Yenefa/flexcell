#!/usr/bin/env python3
"""Repeat the abstention probe several times per case: is the refusal STABLE?

WHY: the first version ran each case once, and I flagged that as a limitation. Last round
established that outcomes in this project flip about a quarter of the time, so a single sample
per case cannot support "the agent refuses impossible tasks" - it can only support "it refused
these once". Repeating costs no robot time and turns a single-sample claim into a rate.
"""
import json
import sys
from pathlib import Path

WT = Path("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp")
sys.path.insert(0, str(WT / "runtime" / "planner"))
sys.path.insert(0, str(WT))
sys.path.insert(0, str(WT / "experiments" / "pilot-001"))
sys.path.insert(0, str(WT / "experiments" / "baselines"))

import importlib.util
spec = importlib.util.spec_from_file_location(
    "ab", WT / "experiments" / "baselines" / "abstention.py")
AB = importlib.util.module_from_spec(spec)
spec.loader.exec_module(AB)

REPEATS = int(sys.argv[1]) if len(sys.argv) > 1 else 3


def main():
    from pilot.llm import Chat
    import agent_planner as ap

    obs_base = {"objects": AB.OBJECTS, "zones": AB.ZONES, "skills": AB.SKILLS}
    results = []
    for case_id, kind, instruction in AB.CASES:
        verdicts = []
        for _ in range(REPEATS):
            obs = dict(obs_base)
            obs["instruction"] = instruction
            plan_obj, problems, raw, usage = ap.plan(obs, Chat())
            try:
                reply = ap.parse_reply(raw) or {}
            except Exception:
                reply = {}
            v, _d = AB.classify(plan_obj, problems, reply)
            verdicts.append(v)
        counts = {v: verdicts.count(v) for v in set(verdicts)}
        stable = len(counts) == 1
        results.append({"case": case_id, "kind": kind, "verdicts": verdicts,
                        "counts": counts, "stable": stable})
        print("%-22s %-10s %-34s %s" % (case_id, kind, ",".join(verdicts),
                                        "STABLE" if stable else "VARIES"))

    imp = [x for x in results if x["kind"] == "IMPOSABLE"]
    pos = [x for x in results if x["kind"] == "POSSIBLE"]
    confident = sum(x["counts"].get("CONFIDENT", 0) for x in imp)
    trials = len(imp) * REPEATS
    print()
    print("repeats per case             :", REPEATS)
    print("impossible case-trials       :", trials)
    print("  CONFIDENTLY ANSWERED       : %d   <- must stay 0" % confident)
    print("  refused or flagged         : %d" % (trials - confident))
    print("impossible cases that VARIES : %d/%d" % (
        sum(1 for x in imp if not x["stable"]), len(imp)))
    pos_ok = sum(x["counts"].get("CONFIDENT", 0) + x["counts"].get("FLAGGED", 0)
                 for x in pos)
    print("possible controls answered   : %d/%d" % (pos_ok, len(pos) * REPEATS))
    print()
    if confident == 0:
        print("READING: across %d trials the planner never answered an impossible" % trials)
        print("instruction confidently. The single-sample result was not a lucky draw.")
    else:
        print("READING: a confidently-answered impossible instruction appeared, so the")
        print("single-sample claim was too strong.")
    Path("/tmp/abstention_repeats.json").write_text(
        json.dumps({"repeats": REPEATS, "results": results}, indent=2) + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
