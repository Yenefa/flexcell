#!/usr/bin/env python3
"""Verify the held-out result: the in-sample rule does not generalise."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    rows = []
    for i in range(10):
        p = HERE / ("s%d.json" % i)
        if p.exists():
            rows.append(json.loads(p.read_text(encoding="utf-8")))
    assert len(rows) == 10, len(rows)

    ok = [r for r in rows if r["official_success"]]
    assert ok == [], ("the held-out suite now passes; rewrite the conclusion", len(ok))

    # every one chose the lateral approach: the rule did transfer, the policy did not
    assert all(r["mode"] == "side_x" for r in rows), [r["mode"] for r in rows]

    # and they are grasp failures by the criterion established last round (<=10 mm vs hundreds)
    errs = [r["release_xy_error_m"] for r in rows]
    assert min(errs) > 0.1, errs

    print(json.dumps({
        "verdict": "EVOBOT_LIBERO_HELDOUT_ZERO_OF_TEN",
        "in_sample_object_suite": "3/5 (threshold chosen on these)",
        "held_out_spatial_suite": "0/10 with the threshold frozen",
        "selected_mode_all_tasks": "side_x",
        "release_errors_mm": [round(1000 * e, 1) for e in errs],
        "mechanism": "objects knocked away, not mis-placed - same detector as last round",
        "conclusion": "the 3/5 was a fit to five samples, not a capability",
        "parser_extension_disclosed": True,
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
