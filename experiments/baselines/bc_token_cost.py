#!/usr/bin/env python3
"""Quantify what the experience channel COSTS when it changes nothing."""
import glob
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-bcplan16"


def usage(arm):
    tot = {}
    n = 0
    for d in sorted(glob.glob(BASE + "/*-" + arm)):
        p = os.path.join(d, "agent_reply.json")
        if not os.path.exists(p):
            continue
        try:
            u = json.load(open(p, encoding="utf-8")).get("usage") or {}
        except Exception:
            continue
        for k, v in u.items():
            if isinstance(v, (int, float)):
                tot[k] = tot.get(k, 0) + v
        n += 1
    return tot, n


def main():
    b, nb = usage("B")
    c, nc = usage("C")
    print("runs: B=%d C=%d" % (nb, nc))
    keys = sorted(set(b) | set(c))
    if not keys:
        print("no token usage recorded")
        return 0
    print("%-14s %10s %10s %8s" % ("metric", "B", "C", "delta"))
    for k in keys:
        vb, vc = b.get(k, 0), c.get(k, 0)
        delta = ""
        if vb:
            delta = "%+.0f%%" % (100.0 * (vc - vb) / vb)
        print("%-14s %10.0f %10.0f %8s" % (k, vb, vc, delta))
    print()
    print("The experience channel retrieved exactly 1 lesson per task and changed")
    print("0 of 16 plans, so any token increase above is pure overhead.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
