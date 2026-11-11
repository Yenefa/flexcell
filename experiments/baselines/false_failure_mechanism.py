#!/usr/bin/env python3
"""Dump the per-instance mechanism for a task-level false failure.

A false failure is: the FSM's own task.out says outcome != 0, while the independent
evaluator on the measured world says passed. This prints the evidence that separates the two
readings - what the skill claimed, where the box actually ended up, and what the verifier
measured - so the mechanism is auditable rather than asserted.
"""
import json
import math
import sys


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def main():
    for oid in sys.argv[1:]:
        d = "/tmp/evobot-batch2/" + oid
        print("######## " + oid)
        spec = read("/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/"
                    "benchmark/held_out/recovery_public64/" + oid + ".json") or {}
        zones = {z["name"]: z for z in spec.get("zones", [])}
        print("-- zone centres")
        for name, z in zones.items():
            print("   %-8s centre=%s radius=%s" % (name, z.get("pose"), z.get("radius")))

        print("-- place.jsonl (what the SKILL reported)")
        p = d + "/sim/skills/place.jsonl"
        try:
            for line in open(p, encoding="utf-8", errors="replace"):
                x = json.loads(line.strip())
                print("   obj=%-14s released=%-6s err=%-4s box_after=%s" % (
                    x.get("object_name"), x.get("released"),
                    str(x.get("error_code")), x.get("box_after")))
        except Exception as exc:
            print("   (unreadable: %s)" % exc)

        print("-- ground truth AFTER the failing attempt (what the WORLD looked like)")
        gt = read(d + "/ground_truth_after1.json") or {}
        for name, pose in (gt.get("objects") or {}).items():
            inside = []
            for zname, z in zones.items():
                c = z.get("pose")
                if not c:
                    continue
                dist = math.hypot(pose[0] - c[0], pose[1] - c[1])
                if dist <= z.get("radius", 0):
                    inside.append("%s (%.1f mm from centre)" % (zname, 1000 * dist))
            print("   %-14s pose=%s  inside: %s" % (
                name, [round(v, 4) for v in pose], ", ".join(inside) or "none"))

        print("-- verify.jsonl (what the skill's OWN verifier measured)")
        p = d + "/sim/skills/verify.jsonl"
        try:
            for line in open(p, encoding="utf-8", errors="replace"):
                x = json.loads(line.strip())
                print("   obj=%-14s verified=%-6s error=%.1f mm (tol %.0f mm)" % (
                    x.get("object_name"), x.get("verified"),
                    1000 * (x.get("position_error_m") or 0),
                    1000 * (x.get("tolerance_m") or 0)))
        except Exception as exc:
            print("   (unreadable: %s)" % exc)

        v1 = read(d + "/verdict_after1.json") or {}
        print("-- evaluator: passed=%s failed_clauses=%s" % (
            v1.get("passed"), v1.get("failed_clauses")))
        out = d + "/task.out"
        try:
            t = open(out, encoding="utf-8", errors="replace").read()
            i = t.rfind("RESULT ")
            r = json.loads(t[i + 7:]) if i >= 0 else {}
            print("-- FSM task.out: outcome=%s detail=%r" % (
                r.get("outcome"), r.get("detail")))
        except Exception as exc:
            print("-- FSM task.out unreadable: %s" % exc)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
