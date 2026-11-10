#!/usr/bin/env python3
"""Scan every archived batch for failure signatures the proposal generator can act on."""
import glob
import json
import os
import sys
from collections import Counter

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ACC = os.path.join(WT, "setup", "acceptance")


def sig(detail):
    d = (detail or "").lower()
    if "occupied destination" in d or "destination occupied" in d:
        return "occupied_destination"
    if "state drift" in d:
        return "state_drift"
    if "unconfirmed" in d:
        return "unconfirmed"
    return "other"


def main():
    total = Counter()
    per_batch = []
    for batch in sorted(os.listdir(ACC)):
        bdir = os.path.join(ACC, batch)
        if not os.path.isdir(bdir) or not batch.startswith("evobot"):
            continue
        c = Counter()
        for t in glob.glob(os.path.join(bdir, "**", "task*.out"), recursive=True):
            txt = open(t, encoding="utf-8", errors="replace").read()
            if "RESULT " not in txt:
                continue
            try:
                r = json.loads(txt.split("RESULT ", 1)[1])
            except json.JSONDecodeError:
                continue
            if r.get("error_code") in (0, None):
                continue
            c[sig(r.get("detail"))] += 1
        if c:
            per_batch.append((batch, dict(c)))
            total.update(c)
    for b, c in per_batch:
        print("%-42s %s" % (b, c))
    print()
    print("TOTAL:", dict(total))
    print("batches with >=2 occupied_destination:",
          [b for b, c in per_batch if c.get("occupied_destination", 0) >= 2])
    return 0


if __name__ == "__main__":
    sys.exit(main())
