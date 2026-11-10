#!/usr/bin/env python3
"""Generate a RECOVERY-focused held-out set.

WHY: the recovery experiment had a denominator of 2, which is not evidence. T13 puts
BOTH objects in the SAME bin, which reliably produces an execution-layer occupancy
failure on the second stage - exactly the condition recovery exists to handle. Using
T13 instances gives a large enough denominator to measure a recovery RATE.

These are fresh seeds, sealed under the same scheme as the rest of held-out.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "benchmark" / "generators"))
import unseen_tasks as U

SEEDS = [7100, 7101, 7102, 7103, 7104, 7105, 7106, 7107]


def main(argv=None):
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for seed in SEEDS:
        spec = U.generate("T13_geometric_conditional", seed, "held_out")
        spec.pop("_branch_note", None)
        (out / (spec["task_id"] + ".json")).write_text(
            json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print("staged", len(list(out.glob("*.json"))), "recovery-set specs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
