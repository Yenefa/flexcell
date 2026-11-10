#!/usr/bin/env python3
"""Three-arm planning comparison on the same 16 sealed instances.

WHY: the mission requires three baselines (FSM / runtime agent / self-evolving), but
A-prime had only ever been run on T01/T02/T04/T05. It had never faced the 16 unseen
instances that B and C were measured on, so the three-arm claim was incomplete.

A-prime is deterministic and needs no model or simulator, so this comparison is cheap and
exact: every arm receives the SAME observation object that B used.
"""
import glob
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "experiments", "baselines"))
import baseline_a_prime_rules as AP

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-bcplan16"


def main():
    dirs = sorted(glob.glob(os.path.join(BASE, "*-B")))
    rows = []
    for d in dirs:
        oid = os.path.basename(d).rsplit("-", 1)[0]
        obs = json.load(open(os.path.join(d, "observation_input.json"), encoding="utf-8"))
        try:
            plan = AP.plan(obs)
            moves = plan.get("moves") or []
            rows.append((oid, "PARSED", len(moves), plan.get("rule")))
        except AP.Unparsed as exc:
            rows.append((oid, "UNPARSED", 0, str(exc)[:60]))
        except Exception as exc:
            rows.append((oid, "ERROR", 0, "%s: %s" % (type(exc).__name__, exc)))
    print("%-20s %-9s %-6s %s" % ("instance", "A-prime", "moves", "rule / reason"))
    for oid, status, n, why in rows:
        print("%-20s %-9s %-6d %s" % (oid, status, n, why))
    parsed = sum(1 for r in rows if r[1] == "PARSED")
    print()
    print("A-prime parsed : %d/%d" % (parsed, len(rows)))
    print("A-prime refused: %d/%d" % (len(rows) - parsed, len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
