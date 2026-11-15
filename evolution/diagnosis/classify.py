#!/usr/bin/env python3
"""Failure attribution from MEASURED evidence (experiment protocol rule 5).

The rule exists because the previous track published three wrong root causes; each was
a plausible story told before reading the data. This classifier only emits a class when
the evidence dict contains the discriminator for it. Otherwise it emits UNKNOWN.

It is deliberately conservative: UNKNOWN is better than a confident wrong story.
"""
import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from runtime.recovery.failure_classification import classify


def main(argv=None):
    argv = argv or sys.argv[1:]
    evidence = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    cls, why = classify(evidence)
    print(json.dumps({"failure_class": cls, "measured_reason": why}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
