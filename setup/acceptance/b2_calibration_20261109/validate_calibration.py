#!/usr/bin/env python3
"""Offline check of the calibration artefact: deterministic train/test split.

Rows are ordered as collected; even indices form the fit set, odd indices the
held-out set. Bins are fitted on the fit set only (same rule as
build_calibration.py), then the held-out rows are used to measure:
  - agreement accuracy of the calibrated probability in each bin,
  - the routing decision at tau=0.85 (fast vs escalate),
  - ECE of the fitted bins against held-out labels.
No model calls here; this is a check of the artefact, not new evidence about
the robot.
"""
import json
import math
import sys
from pathlib import Path

Z = 1.959963984540054


def wilson_lower(agree, n):
    if n == 0:
        return 0.0
    p = agree / n
    denom = 1 + Z * Z / n
    centre = p + Z * Z / (2 * n)
    spread = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return max(0.0, (centre - spread) / denom)


def fit(rows, bins=10):
    width = 1.0 / bins
    out = []
    for i in range(bins):
        lower = round(i * width, 6)
        upper = round((i + 1) * width, 6) if i + 1 < bins else 1.0
        members = [r for r in rows if lower <= r["reported_confidence"] < upper
                   or (upper == 1.0 and r["reported_confidence"] == 1.0)]
        agree = sum(1 for r in members if r["agree"])
        out.append({"lower": lower, "upper": upper, "n": len(members),
                    "agree": agree, "wilson_lower": wilson_lower(agree, len(members)),
                    "rate": (agree / len(members)) if members else 0.0})
    return out


def bin_for(bins, value):
    for b in bins:
        if b["lower"] <= value < b["upper"] or (value == 1.0 and b["upper"] == 1.0):
            return b
    return None


def main(rows_path, out_path):
    rows = [json.loads(line) for line in Path(rows_path).read_text().splitlines() if line.strip()]
    fit_rows = rows[::2]
    test_rows = rows[1::2]
    bins = fit(fit_rows)
    routed = escalated = correct = 0
    ece_terms = []
    for r in test_rows:
        b = bin_for(bins, r["reported_confidence"])
        usable = b is not None and b["n"] >= 5 and b["wilson_lower"] >= 0.85
        if usable:
            routed += 1
            correct += 1 if r["agree"] else 0
            ece_terms.append(abs(b["rate"] - (1 if r["agree"] else 0)))
        else:
            escalated += 1
    report = {
        "rows": len(rows), "fit": len(fit_rows), "test": len(test_rows),
        "bins_fit": [b for b in bins if b["n"]],
        "test_routed_to_fast": routed,
        "test_escalated": escalated,
        "routed_agreement": (correct / routed) if routed else None,
        "routed_errors": routed - correct,
        "mean_abs_bin_error_on_routed": (sum(ece_terms) / len(ece_terms)) if ece_terms else None,
        "note": "labels are FSM agreement, not physical success; routing check only",
    }
    Path(out_path).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
