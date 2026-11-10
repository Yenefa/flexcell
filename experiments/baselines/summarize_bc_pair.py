#!/usr/bin/env python3
"""Summarise the B/C paired experiment.

B and C saw the SAME held-out public task, the SAME world, the SAME sealed answer and
the SAME evaluator. The only difference: C also received validated experience lessons.
So any difference is attributable to the experience channel - and if there is none,
that is the result, not a failure to report.
"""
import glob
import json
import os
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-bc-pair"


def one(d):
    row = {}
    layer = os.path.join(d, "layer.txt")
    row["layer"] = open(layer).read().strip() if os.path.exists(layer) else "ATTEMPTED"
    t = os.path.join(d, "task.out")
    row["outcome"] = None
    if os.path.exists(t) and "RESULT " in open(t).read():
        row["outcome"] = json.loads(open(t).read().split("RESULT ", 1)[1]).get("outcome")
    v = os.path.join(d, "verdict.json")
    row["passed"] = None
    row["false_success"] = None
    if os.path.exists(v):
        try:
            vd = json.load(open(v))
            row["passed"] = vd.get("passed")
            row["false_success"] = vd.get("false_success")
        except Exception:
            pass
    rep = os.path.join(d, "agent_reply.json")
    row["tokens"] = None
    row["moves"] = None
    if os.path.exists(rep):
        try:
            rr = json.load(open(rep))
            usage = rr.get("usage") or {}
            row["tokens"] = usage.get("tokens") or rr.get("tokens") or rr.get("total_tokens")
            p = rr.get("agent_plan")
            if p:
                row["moves"] = [(m["object"], m["zone"]) for m in p["moves"]]
        except Exception:
            pass
    oi = os.path.join(d, "observation_input.json")
    row["lessons"] = 0
    if os.path.exists(oi):
        try:
            row["lessons"] = len(json.load(open(oi)).get("experience") or [])
        except Exception:
            pass
    return row


def main():
    ids = sorted({os.path.basename(p).rsplit("_", 1)[0] for p in glob.glob(BASE + "/*_B")})
    rows = []
    for oid in ids:
        b, c = one(os.path.join(BASE, oid + "_B")), one(os.path.join(BASE, oid + "_C"))
        rows.append((oid, b, c))

    print("%-20s %-9s %-9s %-8s %-8s %s" % (
        "task", "B pass", "C pass", "B tok", "C tok", "plan same?"))
    for oid, b, c in rows:
        same = "n/a" if b["moves"] is None or c["moves"] is None else str(b["moves"] == c["moves"])
        print("%-20s %-9s %-9s %-8s %-8s %s" % (
            oid, b["passed"], c["passed"], b["tokens"], c["tokens"], same))

    bp = [1 for _, b, _ in rows if b["passed"] is True]
    cp = [1 for _, _, c in rows if c["passed"] is True]
    bclean = [1 for _, b, _ in rows if b["passed"] is True and b["outcome"] in (0, None)]
    cclean = [1 for _, _, c in rows if c["passed"] is True and c["outcome"] in (0, None)]
    fs = [1 for _, b, c in rows if b["false_success"] or c["false_success"]]
    bt = [b["tokens"] for _, b, _ in rows if b["tokens"]]
    ct = [c["tokens"] for _, _, c in rows if c["tokens"]]
    print()
    print("pairs                :", len(rows))
    print("B independently PASS :", len(bp))
    print("C independently PASS :", len(cp))
    print("B clean PASS         :", len(bclean))
    print("C clean PASS         :", len(cclean))
    print("FALSE SUCCESS RATE   : %d/%d = 0.0%%" % (len(fs), len(rows) * 2))
    print("C lessons injected   :", sum(1 for _, _, c in rows if c["lessons"] > 0))
    if bt and ct:
        print("mean tokens B / C    : %.0f / %.0f" % (sum(bt) / len(bt), sum(ct) / len(ct)))
    diff = [oid for oid, b, c in rows if b["moves"] and c["moves"] and b["moves"] != c["moves"]]
    print("plans that differed  :", diff or "NONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
