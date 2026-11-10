#!/usr/bin/env python3
"""Verify the first B/C paired batch (superseded: it ran at ceiling)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    b = sorted((HERE / "runs").glob("*_B"))
    c = sorted((HERE / "runs").glob("*_C"))
    assert len(b) == 6 and len(c) == 6, (len(b), len(c))
    identical = 0
    for d in b:
        oid = d.name.rsplit("_", 1)[0]
        pc = HERE / "runs" / (oid + "_C") / "plan.json"
        if (d / "plan.json").read_bytes() == pc.read_bytes():
            identical += 1
    assert identical == 6, identical
    line = (HERE / "plan_identity.txt").read_text(encoding="utf-8")
    assert line.count("SAME") == 6
    print(json.dumps({
        "verdict": "EVOBOT_BC_PAIR_AT_CEILING_VERIFIED",
        "pairs": 6,
        "byte_identical_plans": identical,
        "why_superseded": "v0.1 held-out was at ceiling; ceiling removed in unseen batch",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
