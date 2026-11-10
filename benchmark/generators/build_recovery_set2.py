#!/usr/bin/env python3
"""Generate a SECOND 16-instance held-out set on fresh seeds.

WHY: the 4/16 actuator-stall rate and the 3/4 recovery rate both rest on n=16, whose 95%
interval is far too wide to claim anything (25% spans roughly 7%-52%). Doubling n with
unseen seeds is the cheapest honest way to narrow it, and it also grows the recovery
denominator, which has never exceeded 4.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "benchmark" / "generators"))
import unseen_tasks as U

T13_SEEDS = [7300, 7301, 7302, 7303, 7304, 7305, 7306, 7307]
T12_SEEDS = [7400, 7401, 7402, 7403, 7404, 7405, 7406, 7407]


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for template, seeds in (("T13_geometric_conditional", T13_SEEDS),
                             ("T12_triple_revisit", T12_SEEDS)):
        for seed in seeds:
            spec = U.generate(template, seed, "held_out")
            spec.pop("_branch_note", None)
            (out / (spec["task_id"] + ".json")).write_text(
                json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print("staged", len(list(out.glob("*.json"))), "specs on fresh seeds")
    return 0


if __name__ == "__main__":
    sys.exit(main())
