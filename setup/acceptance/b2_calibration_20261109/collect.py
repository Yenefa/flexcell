#!/usr/bin/env python3
"""Collect fast-arm decisions with the FSM-agreement label (B2 calibration pilot).

Replays archived E-021 policy inputs through the CURRENT fast-arm backend
(any OpenAI-compatible endpoint), records the reported confidence and whether
the fast choice agrees with the frozen FSM policy on the same input, then
writes rows.jsonl plus a summary. This is real model output, not synthetic
labels. No calibration artefact is produced until every bin has enough rows.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src" / "flexcell" / "flexcell_skills"))

from flexcell_skills.canonical_state import deserialize_envelope  # noqa: E402
from flexcell_skills.confidence_calibration import prompt_digest  # noqa: E402
from flexcell_skills.contracts.episode import (  # noqa: E402
    _constraints_from_dict, _goal_from_dict, _history_from_dicts)
from flexcell_skills.decision_policy import FSMPolicy, PolicyStateError  # noqa: E402
from flexcell_skills.jev_backends import LocalReproductionBackend  # noqa: E402
from flexcell_skills.jev_policy import JevPolicy  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes-dir", required=True)
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    endpoint = os.environ.get("FLEXCELL_JEV_ENDPOINT", "")
    model = os.environ.get("FLEXCELL_JEV_MODEL", "")
    if not endpoint or not model or not os.environ.get("FLEXCELL_JEV_API_KEY"):
        print("missing FLEXCELL_JEV_ENDPOINT / FLEXCELL_JEV_MODEL / FLEXCELL_JEV_API_KEY")
        return 2

    backend = LocalReproductionBackend(timeout_s=30)
    fast = JevPolicy(backend, timeout_s=30)
    fsm = FSMPolicy()

    rows = []
    for path in sorted(Path(args.episodes_dir).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for step in doc.get("steps", []):
            pi = step.get("policy_input") or {}
            out = step.get("policy_output") or {}
            trace = out.get("policy_trace") or {}
            if pi.get("world_state_canonical") is None:
                continue
            if trace.get("source") not in ("jev", "llm"):
                continue
            rows.append((path.name, step.get("seq"), pi))
    if not rows:
        print("no routed decisions found")
        return 2

    step = max(1, len(rows) // args.n)
    picked = rows[::step][: args.n]
    collected = []
    skipped = 0
    for name, seq, pi in picked:
        deserialize_envelope(pi["world_state_canonical"])
        world = json.loads(pi["world_state_canonical"])
        goal = _goal_from_dict(pi["goal"])
        constraints = _constraints_from_dict(pi["constraints"])
        history = _history_from_dicts(pi["history"])
        decision = fast.decide(world, goal, constraints, history)
        try:
            fsm_decision = fsm.decide(world, goal, constraints, history)
        except PolicyStateError:
            # mid-leg history from a different trajectory: the FSM grammar
            # cannot label this step, so it is excluded (counted, not faked).
            skipped += 1
            continue
        trace = decision.policy_trace or {}
        collected.append({
            "episode": name, "seq": seq,
            "choice": decision.action,
            "reported_confidence": float(decision.confidence),
            "confidence_label": trace.get("confidence_label"),
            "calibrated": bool(trace.get("confidence_calibrated")),
            "fsm_action": fsm_decision.action,
            "agree": bool(decision.action == fsm_decision.action),
            "tokens": int((trace.get("tokens") or 0)),
        })

    agree = sum(1 for r in collected if r["agree"])
    summary = {
        "n": len(collected), "agree": agree,
        "agreement_rate": agree / len(collected),
        "model": model, "endpoint_host": endpoint.split("/")[2],
        "prompt_sha256": prompt_digest(),
        "identity_sha256": hashlib.sha256(
            ("%s|%s|%s" % (endpoint, model, prompt_digest())).encode()).hexdigest(),
        "label_skipped": skipped,
        "reasoning": "FSM_ACTION_AGREEMENT",
        "calibration_artefact": "not built (pilot: bins have too few samples)",
        "note": "confidence is FSM-agreement estimate, never physical success odds",
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "rows.jsonl").write_text(
        "\n".join(json.dumps(r, sort_keys=True) for r in collected) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
