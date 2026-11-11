#!/usr/bin/env python3
"""Can the model judge whether a PLAN satisfies an INSTRUCTION?

WHY THIS IS THE MISSING PIECE: the two-condition measurement check verifies that the world followed
the plan, and was demonstrated - with a borrowed plan - to call a wrong plan "satisfied" and so
produce a false success. To use that check safely, something must judge plan-versus-instruction,
and that is exactly what a model can do and a regex cannot.

THE TEST NEEDS BOTH DIRECTIONS. A judge that always says "yes" is worthless, and a judge that
always says "no" is useless. So each instance is presented twice:
  OWN  plan  - the plan the agent actually produced for this instruction (should satisfy)
  DONOR plan - a real plan produced for a DIFFERENT instance of the same template, which puts the
               blocks in the other bin (should not satisfy)
The judge sees only the instruction and the plan, never the answer.

If OWN and DONOR separate cleanly this becomes the gate the claim check lacks. If they do not,
the deterministic check stays unusable and that is the honest outcome.
"""
import json
import os
import sys
from pathlib import Path

WT = Path("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp")
sys.path.insert(0, str(WT / "experiments" / "pilot-001"))

PUBDIR = WT / "benchmark" / "held_out" / (sys.argv[1] if len(sys.argv) > 1
                                              else "recovery_public80")
BATCH = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/evobot-batch4")
REPEATS = int(sys.argv[3]) if len(sys.argv) > 3 else 1
# the bin radius is part of what the agent observes, so telling the judge is not a leak
RADIUS_M = 0.06

SYSTEM = """You audit robot plans.

You will be given a task instruction and a plan. Decide only this: if this plan were executed
exactly as written, would the resulting world satisfy the instruction?

You are NOT asked whether the plan is executable, tidy, or well explained. You are NOT told the
intended answer. Judge only correspondence between the instruction's words and the plan's moves.

Reply with JSON only:
{"satisfies": true|false, "why": "<one sentence naming the specific mismatch, or 'matches'>"}"""


def describe(instruction, plan, colours=None, zones=None):
    """Render the plan so a reader can match it to the instruction.

    The first version printed only the internal names (target_box_a/b) while the instructions
    say "red block" and "blue block". The judge then failed three OWN plans for "not specifying
    which colour" - a defect in MY rendering, not in its judgement. The colour is a perceived
    property of the object, not a hint, so printing it leaks nothing.
    """
    colours = colours or {}
    lines = ["Instruction:", instruction.strip(), "", "Plan:"]
    for i, st in enumerate(plan.get("stages", []), 1):
        pose = st.get("place_pose") or [0, 0, 0]
        name = st.get("object_name")
        colour = colours.get(name)
        label = ("%s (%s)" % (name, colour)) if colour else name
        lines.append("  %d. put %s at x=%.3f y=%.3f" % (i, label, pose[0], pose[1]))
    lines.append("")
    lines.append("Robot frame: +y is the robot LEFT, -y is the robot RIGHT, +x is forward.")
    lines.append("The two bins are DISCS: the right bin is centred at x=0.120 y=-0.150 and "
                 "the left bin at x=0.250 y=0.050.")
    lines.append("A block counts as being in a bin when it is within the bin radius of that "
                 "centre:")
    for z, label in (("zone_1", "right"), ("zone_2", "left")):
        info = (zones or {}).get(z)
        if info:
            lines.append("  %s bin: centre x=%.3f y=%.3f, radius %.3f m"
                         % (label, info[0], info[1], RADIUS_M))
    lines.append("A plan with several stages for one object is a SEQUENCE: each stage is a "
                 "place that must be visited in order, and the object ends wherever the "
                 "last stage leaves it.")
    return "\n".join(lines)


def ask(chat, user):
    resp = chat.chat([{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": user}])
    raw = resp.get("content") if isinstance(resp, dict) else resp[0]
    try:
        start = raw.index("{")
        return json.loads(raw[start:raw.rindex("}") + 1])
    except Exception:
        return {"satisfies": None, "why": "unparseable: " + str(raw)[:80]}


def main():
    from pilot.llm import Chat
    pubs = sorted(PUBDIR.glob("*.json"))
    specs = []
    for p in pubs:
        d = json.loads(p.read_text(encoding="utf-8"))
        plan_p = BATCH / d["task_id"] / "plan.json"
        if not plan_p.exists():
            continue
        colours = {o["name"]: o.get("color") for o in d.get("objects", [])}
        zones = {"zone_1": [0.12, -0.15], "zone_2": [0.25, 0.05]}
        specs.append({"id": d["task_id"], "instruction": d["instruction"],
                      "colours": colours, "zones": zones,
                      "plan": json.loads(plan_p.read_text(encoding="utf-8"))})
    if len(specs) < 4:
        print("not enough instances")
        return 0

    def zone_of(plan):
        poses = [st["place_pose"] for st in plan.get("stages", []) if st.get("place_pose")]
        if not poses:
            return None
        left = sum(1 for q in poses if q[1] > -0.05)
        return "left" if left > len(poses) / 2 else "right"

    rows = []
    for i, s in enumerate(specs):
        own_zone = zone_of(s["plan"])
        donor = next((t for t in specs if zone_of(t["plan"]) != own_zone), None)
        if donor is None:
            continue
        for kind, plan in (("OWN", s["plan"]), ("DONOR", donor["plan"])):
            for _ in range(REPEATS):
                verdict = ask(Chat(), describe(s["instruction"], plan, s["colours"],
                                           s["zones"]))
                rows.append({"id": s["id"], "kind": kind,
                             "satisfies": verdict.get("satisfies"),
                             "why": str(verdict.get("why"))[:80]})
                print("%-22s %-6s satisfies=%-6s %s" % (s["id"], kind,
                                                        verdict.get("satisfies"),
                                                        str(verdict.get("why"))[:64]))

    own = [r for r in rows if r["kind"] == "OWN"]
    don = [r for r in rows if r["kind"] == "DONOR"]
    own_yes = sum(1 for r in own if r["satisfies"] is True)
    don_no = sum(1 for r in don if r["satisfies"] is False)
    print()
    print("OWN   plans judged satisfying : %d/%d" % (own_yes, len(own)))
    print("DONOR plans judged NOT satisfying: %d/%d" % (don_no, len(don)))
    acc = (own_yes + don_no) / max(1, len(rows))
    print("separation accuracy           : %.1f%%" % (100 * acc))
    print()
    if own_yes == len(own) and don_no == len(don):
        print("READING: the judge separates the two directions cleanly on this sample, so it")
        print("could supply the plan-versus-instruction gate the measurement check lacks.")
    else:
        print("READING: the judge does NOT separate cleanly, so it cannot be used as that gate")
        print("yet, and the deterministic claim check stays unusable.")
    Path("/tmp/plan_judge.json").write_text(json.dumps(rows, indent=2) + "\n",
                                            encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
