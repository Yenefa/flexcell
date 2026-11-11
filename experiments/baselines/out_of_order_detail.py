#!/usr/bin/env python3
"""Show, for each out-of-order run, that the plan had the right sequence and execution lost it.

This is the interesting failure mode of a temporal constraint: it is not that the agent failed
to understand the requirement, it is that the understanding did not survive execution.
"""
import json
import sys
from pathlib import Path


def main():
    for oid in sys.argv[1:]:
        d = Path("/tmp/evobot-batch4") / oid
        print("--- " + oid)
        plan = json.loads((d / "plan.json").read_text(encoding="utf-8"))
        planned = [s.get("object_name") for s in plan.get("stages", [])]
        print("  planned order :", planned)
        obs_p = d / "observation_after1.json"
        if obs_p.exists():
            obs = json.loads(obs_p.read_text(encoding="utf-8"))
            print("  observed order:", obs.get("move_sequence"))
        v = json.loads((d / "verdict_after1.json").read_text(encoding="utf-8"))
        for c in v.get("clauses", []):
            if c.get("clause") == "order":
                print("  order clause  :", json.dumps(c))
        vv = d / "verdict.json"
        if vv.exists():
            fin = json.loads(vv.read_text(encoding="utf-8"))
            print("  final passed  :", fin.get("passed"))
        retry = d / "plan_retry.json"
        print("  retried       :", retry.exists())
    return 0


if __name__ == "__main__":
    sys.exit(main())
