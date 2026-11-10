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
    """Return validated lessons that can actually change a PLAN.

    Routing rule, added after two B/C experiments measured byte-identical plans: the
    agent plan is {moves:[{object, zone}], unmoved}, so it has no landing coordinates.
    A lesson about landing spots or harness concerns CANNOT change a plan from inside the
    prompt - it is already implemented in spread_destinations.py / cyclonedds.xml. Those
    lessons are therefore not retrieved into the prompt any more; advertising them there
    only cost tokens and changed nothing.

    Retrieval is keyed on the instruction text, never on task answers: the public
    held-out task carries no template id, so no lookup may depend on one.
    """
    ok, _ = store.verify_chain(store_path)
    if not ok:
        raise RuntimeError("experience chain is broken; refusing to learn from it")
    rows = [r for r in store.read(store_path) if r.get("validated")]
    text = observation["instruction"].lower()
    scored = []
    for r in rows:
        if not _is_planner_actionable(r.get("lesson", "")):
            continue
        score = 0
        for word in ("right", "left", "bin", "order", "except", "further", "passing"):
            if word in text and word in r.get("lesson", "").lower():
                score += 1
        # A lesson about a REQUIRED plan field applies to every task, so it must not
        # depend on keyword luck. Measured bug: "Declare exactly the objects present"
        # mentions no task keyword, so its score was always 0 and the only
        # planner-actionable lesson in the store could NEVER be retrieved. The
        # experience channel was empty by construction, not by irrelevance.
        lesson_text = r.get("lesson", "").lower()
        if any(f in lesson_text for f in _REQUIRED_FIELDS):
            score += 1
        scored.append((score, r))
    scored.sort(key=lambda x: (-x[0], x[1].get("record_sha256", "")))
    return [r for s, r in scored[:limit] if s > 0]


# Words that mean a lesson is about a downstream or harness concern the planner cannot
# express. Keep in sync with evolution/transfer/route_lessons.py.
_REQUIRED_FIELDS = ("unmoved", "object", "zone", "declare")

_NON_PLANNER = ("landing", "spot", "centre", "center", "domain", "participant",
                "admission", "launch", "stack", "pose", "spread")


def _is_planner_actionable(lesson):
    text = (lesson or "").lower()
    return not any(w in text for w in _NON_PLANNER)


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
