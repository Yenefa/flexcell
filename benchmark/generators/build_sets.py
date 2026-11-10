#!/usr/bin/env python3
"""Materialise the EvoBot benchmark instance sets.

Seeds are fixed so the sets are reproducible: regenerating from these seeds must
produce byte-identical specs (the tests assert determinism). Held-out specs are
written to benchmark/held_out/, which the agent runtime is forbidden to read - the
evaluator needs them, the agent does not.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark" / "generators"))

import generate as gen

# Disjoint seed ranges per split, so no instance can leak between them.
SPLITS = {
    "train": (1000, 12),
    "val": (2000, 6),
    "held_out": (9000, 6),
}


def main():
    manifest = {"generator_version": gen.GENERATOR_VERSION,
                "evaluator_version": gen.EVALUATOR_VERSION, "splits": {}}
    total = 0
    for split, (base, count) in SPLITS.items():
        out_dir = ROOT / "benchmark" / ("held_out" if split == "held_out" else "tasks") / split
        out_dir.mkdir(parents=True, exist_ok=True)
        ids = []
        for template in sorted(gen.TEMPLATES):
            for i in range(count):
                seed = base + i
                spec = gen.generate(template, seed, split)
                name = "%s.json" % spec["task_id"]
                (out_dir / name).write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
                ids.append(spec["task_id"])
                total += 1
        manifest["splits"][split] = {"count": len(ids), "instances": ids}
        print("%-9s %d instances -> %s" % (split, len(ids), out_dir))
    (ROOT / "benchmark" / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print("total:", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
