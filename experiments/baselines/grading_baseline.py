#!/usr/bin/env python3
"""Capture the grading contract BEFORE changing the observation bridge.

Reuses sealed_evaluate.load_full_spec so the full spec (public + sealed answer) is
reconstructed the same way the real grader does. Only the GRADING part is fingerprinted:
passed, clause names and their ok flags. The claim-derived booleans are excluded on
purpose, because the claim plumbing is exactly what is about to change.

Run with privilege.
"""
import glob
import hashlib
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "benchmark", "evaluators"))
import evaluate as E                                   # noqa: E402
import sealed_evaluate as SE                           # noqa: E402


def main():
    out = sys.argv[1]
    rows = {}
    for base in ("/tmp/evobot-pair16", "/tmp/evobot-pair32"):
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            obs_p = os.path.join(d, "observation.json")
            if not os.path.exists(obs_p):
                continue
            task_id = os.path.basename(d)
            pub = None
            for pubname in ("recovery_public16", "recovery_public32"):
                cand = os.path.join(WT, "benchmark", "held_out", pubname,
                                    task_id + ".json")
                if os.path.exists(cand):
                    pub = cand
                    break
            if pub is None:
                continue
            try:
                spec = SE.load_full_spec(pub)
                obs = json.load(open(obs_p, encoding="utf-8"))
                clean = {k: v for k, v in obs.items() if not k.startswith("_")}
                res = E.evaluate(spec, clean)
            except Exception as exc:                   # noqa: BLE001
                print("skip", task_id, exc)
                continue
            grading = {"passed": res["passed"],
                       "clauses": [[c["clause"], c["ok"]] for c in res["clauses"]],
                       "failed_clauses": res["failed_clauses"]}
            rows[task_id] = {
                "grading": grading,
                "grading_sha256": hashlib.sha256(
                    json.dumps(grading, sort_keys=True).encode()).hexdigest(),
            }
    doc = {"record_kind": "EVOBOT_GRADING_BASELINE",
           "why": ("Captured before modifying the observation bridge. Clause structure "
                   "must not move; only claim plumbing may change."),
           "tasks": len(rows), "rows": rows}
    open(out, "w", encoding="utf-8").write(json.dumps(doc, indent=2) + "\n")
    print("captured grading baseline for", len(rows), "tasks ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
