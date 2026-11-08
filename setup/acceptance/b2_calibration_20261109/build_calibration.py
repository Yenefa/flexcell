#!/usr/bin/env python3
"""Build a confidence-calibration artefact from collected fast-arm rows.

Bins are equal-width over the reported confidence; each bin stores n, the
FSM-agreement count and its Wilson 95% lower bound. The schema matches
flexcell_skills.confidence_calibration.ConfidenceCalibration exactly.

Important: for a remote model there is no weight file, so model_sha256 is the
IDENTITY digest recorded by collect.py (endpoint|model|prompt surface), not a
weight digest. The artefact says so explicitly and must not be presented as
weight identity.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "flexcell" / "flexcell_skills"))

from flexcell_skills.confidence_calibration import prompt_digest  # noqa: E402

Z = 1.959963984540054


def wilson_lower(agree, n):
    if n == 0:
        return 0.0
    p = agree / n
    denom = 1 + Z * Z / n
    centre = p + Z * Z / (2 * n)
    spread = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n))
    return max(0.0, (centre - spread) / denom)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--bins", type=int, default=10)
    args = ap.parse_args()

    rows = [json.loads(line) for line in Path(args.rows).read_text(encoding="utf-8").splitlines() if line.strip()]
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    if not rows:
        print("no rows")
        return 2
    width = 1.0 / args.bins
    bins = []
    for i in range(args.bins):
        lower = round(i * width, 6)
        upper = round((i + 1) * width, 6) if i + 1 < args.bins else 1.0
        members = [r for r in rows if lower <= r["reported_confidence"] < upper or (upper == 1.0 and r["reported_confidence"] == 1.0)]
        agree = sum(1 for r in members if r["agree"])
        bins.append({"lower": lower, "upper": upper, "n": len(members),
                     "agree": agree, "wilson_lower": round(wilson_lower(agree, len(members)), 6)})
    artefact = {
        "schema_version": 1,
        "prompt_sha256": prompt_digest(),
        "model": summary["model"],
        "model_sha256": hashlib.sha256(
            ("%s|%s" % (summary["model"], prompt_digest())).encode()).hexdigest(),
        "model_sha256_kind": "remote_identity_endpoint_model_prompt (not weights)",
        "label_definition": "FSM_ACTION_AGREEMENT",
        "label_skipped": summary.get("label_skipped", 0),
        "source_rows": len(rows),
        "bins": bins,
    }
    Path(args.out).write_text(json.dumps(artefact, indent=2) + "\n", encoding="utf-8")
    usable = [b for b in bins if b["n"] >= 5 and b["wilson_lower"] >= 0.85]
    print(json.dumps({"bins": len(bins), "rows": len(rows),
                      "bins_with_n_ge_5": sum(1 for b in bins if b["n"] >= 5),
                      "bins_clearing_0.85": [[b["lower"], b["upper"], b["n"], b["wilson_lower"]] for b in usable],
                      "out": args.out}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
