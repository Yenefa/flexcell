#!/usr/bin/env python3
"""EvoBot Baseline C - self-evolving arm (v0.1).

WHAT MAKES IT "C" here, honestly scoped:
  B plans from instruction + perception only.
  C additionally RETRIEVES validated experience from past failures, and may PROPOSE a
  bounded planner-level change. The proposal is decided by the regression gate, not by
  the agent. C cannot edit evaluators, schemas, tolerances or held-out answers.

NOT YET IMPLEMENTED in v0.1: applying an accepted proposal to source and rebuilding.
That step needs a human-approved write scope, so this arm currently stops at the gate.
Recording that boundary is the point of this file.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "evolution" / "experience"))
sys.path.insert(0, str(WT / "evolution" / "diagnosis"))
sys.path.insert(0, str(WT / "evolution" / "validation"))
sys.path.insert(0, str(WT / "runtime" / "planner"))
sys.path.insert(0, str(WT / "experiments" / "pilot-001"))

import store
import classify as diagnosis
import regress
import agent_planner as ap

DEFAULT_STORE = WT / "evolution" / "experience" / "records.jsonl"


def retrieve(observation, store_path=DEFAULT_STORE, limit=3):
    """Return validated lessons relevant to this observation.

    Retrieval is keyed on the FAILURE CLASS history, not on task answers. The public
    held-out task has no template id, so no lookup can depend on one.
    """
    ok, _ = store.verify_chain(store_path)
    if not ok:
        raise RuntimeError("experience chain is broken; refusing to learn from it")
    rows = [r for r in store.read(store_path) if r.get("validated")]
    text = observation["instruction"].lower()
    scored = []
    for r in rows:
        score = 0
        for word in ("right", "left", "bin", "order", "except", "further", "passing"):
            if word in text and word in r.get("lesson", "").lower():
                score += 1
        scored.append((score, r))
    scored.sort(key=lambda x: (-x[0], x[1].get("record_sha256", "")))
    return [r for s, r in scored[:limit] if s > 0]


def build_observation_with_experience(observation, store_path=DEFAULT_STORE):
    """Return a copy of the observation plus retrieved lessons. Never mutates input."""
    lessons = retrieve(observation, store_path)
    enriched = dict(observation)
    enriched["experience"] = [{"lesson": r["lesson"],
                               "failure_class": r["failure_class"],
                               "source_run": r["source_run"]} for r in lessons]
    return enriched


def propose(record, files, expected_effect, rollback):
    """Wrap an experience record into a gate-checkable proposal."""
    return {"evidence": record.get("evidence"), "files": list(files),
            "expected_effect": expected_effect, "rollback": rollback,
            "based_on": record.get("record_sha256")}


def main(argv=None):
    import argparse
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--observation", required=True)
    ap_.add_argument("--out", required=True)
    args = ap_.parse_args(argv)
    obs = json.loads(Path(args.observation).read_text(encoding="utf-8"))
    enriched = build_observation_with_experience(obs)
    Path(args.out).write_text(json.dumps(enriched, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"retrieved_lessons": len(enriched["experience"]),
                      "lessons": enriched["experience"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
