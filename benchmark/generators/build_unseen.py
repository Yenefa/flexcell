#!/usr/bin/env python3
"""Generate UNSEEN held-out specs into a staging dir OUTSIDE the checkout.

The answers never land in the checkout here. Only the privileged sealing step reads
them, and it writes them to /etc/evobot/sealed.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "benchmark" / "generators"))
import unseen_tasks as U

SEEDS = [7000, 7001, 7002]


def main(argv=None):
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for template in sorted(U.TEMPLATES):
        for seed in SEEDS:
            spec = U.generate(template, seed, "held_out")
            # strip the private branch note so it can never be emitted
            spec.pop("_branch_note", None)
            (out / (spec["task_id"] + ".json")).write_text(
                json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print("staged", len(list(out.glob("*.json"))), "unseen specs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
