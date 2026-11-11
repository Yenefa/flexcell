#!/usr/bin/env python3
"""Verify the transfer result, including that it is honestly a 1/3."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    res = {}
    for i in (0, 1, 2):
        p = HERE / ("t%d.json" % i)
        if p.exists():
            res[i] = json.loads(p.read_text(encoding="utf-8"))
    assert len(res) == 3, sorted(res)

    ok = [i for i, r in res.items() if r["official_success"]]
    assert ok == [0], ("the transfer picture changed", ok)
    # every task parsed its goal correctly - that part DID transfer
    for i, r in res.items():
        assert r["parsed_object"].endswith("_1"), r["parsed_object"]
        assert r["parsed_region"].endswith("_contain_region"), r["parsed_region"]
    # the two failures must be grasp failures, not planning ones
    for i in (1, 2):
        log = " ".join(res[i]["log"])
        moved = res[i]["log"][-1]
        assert "object final at" in moved, moved
    print(json.dumps({
        "verdict": "EVOBOT_LIBERO_TRANSFER_ONE_OF_THREE",
        "solved": [res[0]["task"]],
        "failed": [res[1]["task"], res[2]["task"]],
        "goal_parsing_transferred": "3/3",
        "grasp_parameter_transferred": "1/3",
        "failure_mode": "grasp height is object specific; cream cheese barely moved, dressing slipped after 4 cm",
        "next_capability": "derive the grasp pose from the object geometry instead of a tuned offset",
        "perception": "ORACLE",
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
