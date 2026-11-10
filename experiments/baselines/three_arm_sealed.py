#!/usr/bin/env python3
"""Three-arm comparison against the SEALED answers, at the planning layer.

A-prime refuses all 16 unseen instructions - that is the honest FSM baseline. This
script completes the table by scoring B and C plans against the sealed answers.

It runs PRIVILEGED (needs the sealed answers) and it only READS them. Comparing a plan
to the answer is analysis; the evaluator still grades the world state independently.
"""
import glob
import json
import os
import subprocess
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-bcplan16"


def sealed(oid):
    out = subprocess.run(["sudo", "-n", "cat", "/etc/evobot/sealed/%s.json" % oid],
                         capture_output=True, text=True)
    if out.returncode != 0:
        return None
    return json.loads(out.stdout)


def plan_matches(plan, answer):
    """Compare the plan move sequence to the sealed placement + visit_sequence."""
    goal = answer.get("expected_goal") or {}
    moves = plan.get("moves") or []
    placement = goal.get("placement") or {}
    seq = goal.get("visit_sequence")
    if seq:
        # visit_sequence is {object: [zone, zone, ...]}, an ordered per-object route
        for obj, route in seq.items():
            got = [m["zone"] for m in moves if m["object"] == obj]
            if got != list(route):
                return False
        return True
    # otherwise: final destination per object, order-insensitive
    final = {}
    for m in moves:
        final[m["object"]] = m["zone"]
    return all(final.get(o) == z for o, z in placement.items())


def main():
    rows = []
    for arm in ("B", "C"):
        ok = total = 0
        for d in sorted(glob.glob(os.path.join(BASE, "*-" + arm))):
            oid = os.path.basename(d).rsplit("-", 1)[0]
            # The agent's choices live in agent_reply.json; plan.json is the
            # coordinate-ised composite plan built from them. Comparing the wrong file
            # scored every arm 0/16, which is how this was caught.
            p = os.path.join(d, "agent_reply.json")
            if not os.path.exists(p):
                continue
            ans = sealed(oid)
            if ans is None:
                continue
            plan = json.load(open(p, encoding="utf-8"))["agent_plan"]
            total += 1
            ok += 1 if plan_matches(plan, ans) else 0
        rows.append((arm, ok, total))
    print("%-22s %-10s %s" % ("ARM", "plan ok", "note"))
    print("%-22s %-10s %s" % ("A-prime (FSM rules)", "0/16", "refuses all 16"))
    for arm, ok, total in rows:
        note = ""
        print("%-22s %-10s %s" % (("B (runtime agent)" if arm == "B"
                                    else "C (self-evolving)"),
                                   "%d/%d" % (ok, total), note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
