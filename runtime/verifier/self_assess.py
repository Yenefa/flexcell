#!/usr/bin/env python3
"""Ask the agent to judge its OWN run, so false_success is a real measurement.

WHY THIS EXISTS: the evaluator computes false_success by comparing the agent's claim
against its own verdict. But nothing in the pipeline ever produced a claim, so
agent_claimed_success was always false and the metric was vacuously zero. A metric that
cannot go wrong is not evidence.

The agent is shown the instruction and the MEASURED final positions - the same evidence a
human reviewer gets - and asked whether the task is complete. Its answer is recorded
verbatim and handed to the evaluator, which compares it against its own clauses.
"""
import argparse
import json
import sys
from pathlib import Path

SYSTEM = """You are reviewing a finished robot task.
You receive the instruction, the plan that was executed, and the MEASURED final position
of every object. Decide whether the instruction was actually carried out.

Be strict: a block that is near but outside its bin is not placed; a block that should
not have moved but moved is a failure; a relay that went straight to the destination
did not pass through the intermediate bin.

Reply with JSON only:
{"success": true|false, "because": "<one sentence citing the measured positions>"}"""


def build_user(instruction, plan, observation, zones):
    lines = ["Instruction:", instruction, "", "Plan executed:"]
    for s in plan.get("stages", []):
        lines.append("  %s -> %s" % (s["object_name"],
                                      [round(float(v), 3) for v in s["place_pose"]]))
    lines += ["", "Bins:"]
    for name, pose in (zones or {}).items():
        lines.append("  %s centre = %s radius 0.06" % (name, [round(float(v), 3) for v in pose[:3]]))
    lines += ["", "Measured final positions:"]
    for name, pose in sorted((observation.get("objects") or {}).items()):
        lines.append("  %s at %s" % (name, [round(float(v), 4) for v in pose[:3]]))
    visits = observation.get("visits") or {}
    if visits:
        lines += ["", "Bins each object was actually released into (in order):"]
        for name, seq in sorted(visits.items()):
            lines.append("  %s: %s" % (name, seq))
    lines += ["", "Return JSON only."]
    return "\n".join(lines)


def parse(text):
    t = text.strip()
    if "```" in t:
        for part in t.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                t = part
                break
    a, b = t.find("{"), t.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("no JSON in reply")
    return json.loads(t[a:b + 1])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="run directory from a batch")
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out")
    args = ap.parse_args(argv)

    run = Path(args.run)
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    plan = json.loads((run / "plan.json").read_text(encoding="utf-8"))
    obs = json.loads((run / "observation.json").read_text(encoding="utf-8"))
    zones = {z["name"]: z["pose"] for z in spec["zones"]}

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "experiments" / "pilot-001"))
    from pilot.llm import Chat
    chat = Chat()
    reply = chat.chat([{"role": "system", "content": SYSTEM},
                       {"role": "user", "content": build_user(
                           spec["instruction"], plan, obs, zones)}])
    if isinstance(reply, dict):
        raw = reply.get("content") or ""
    elif isinstance(reply, tuple):
        raw = reply[0]
    else:
        raw = str(reply)
    verdict = parse(raw)
    payload = {"task_id": spec["task_id"], "success": bool(verdict.get("success")),
               "because": str(verdict.get("because", ""))[:400], "raw": raw,
               "source": "agent_self_assessment"}
    out = Path(args.out) if args.out else (run / "self_assessment.json")
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
