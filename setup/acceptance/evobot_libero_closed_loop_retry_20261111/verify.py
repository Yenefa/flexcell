#!/usr/bin/env python3
"""Verify the closed-loop retry result and the sharper diagnosis it produced."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(prefix, i):
    p = HERE / ("%s_%d.json" % (prefix, i))
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    obj = [load("obj", i) for i in range(5)]
    spa = [load("spa", i) for i in range(10)]
    assert all(obj) and all(spa), ([i for i, r in enumerate(obj) if not r],
                                   [i for i, r in enumerate(spa) if not r])

    ok = [i for i, r in enumerate(obj) if r["official_success"]]
    assert ok == [0, 1, 3], ok

    # the retry actually fired on task 3: first attempt failed to grip, second succeeded
    t3 = obj[3]
    assert len(t3["attempts"]) == 2, t3["attempts"]
    assert t3["attempts"][0]["carried"] is False
    assert t3["attempts"][1]["carried"] is True and t3["attempts"][1]["success"] is True

    # held out: still nothing, and the reason is that NO attempt ever grips
    assert [i for i, r in enumerate(spa) if r["official_success"]] == []
    for r in spa:
        assert all(a["carried"] is False for a in r["attempts"]), r["task"]

    print(json.dumps({
        "verdict": "EVOBOT_LIBERO_CLOSED_LOOP_RETRY",
        "in_sample_libero_object": "%d/5, no fitted constant" % len(ok),
        "retry_actually_fired": "task 3: top failed to grip, side_x succeeded",
        "held_out_libero_spatial": "0/10",
        "diagnosis_change": ("not 'the wrong approach was chosen' but 'neither approach grips a "
                             "bowl' - every attempt reports carried=False"),
        "why_retry_cannot_help_there": "the failure is upstream of approach selection",
        "perception": "ORACLE",
        "evaluator_touched": False,
        "llm_involved": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
