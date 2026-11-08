#!/usr/bin/env python3
"""B2 pilot: FSM vs hybrid with the fast arm unavailable (degraded hybrid)."""
import hashlib
import json
from pathlib import Path

HASHES = {
    'fsm/result.json': 'ebb956fa85eb364791c9880bdd74129ea58af7dc5d8a787b915836a2e5d99258',
    'hybrid/result.json': '48c59b3f2004e8d5e515c84783f30763dc5a4922d443411103ffbb272dd1a094',
}


def main():
    here = Path(__file__).parent
    for rel, expected in HASHES.items():
        data = (here / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
        doc = json.loads(data.decode())
        assert doc["status"] == "PASS", rel
        assert doc["task"]["outcome"] == "OUTCOME_SUCCEEDED", rel
    fsm = json.loads((here / "fsm/episode.json").read_text())
    hyb = json.loads((here / "hybrid/episode.json").read_text())
    assert fsm["initial_world_state"], "fsm episode lacks initial world state"
    assert hyb["initial_world_state"], "hybrid episode lacks initial world state"
    traces = [(s.get("policy_output") or {}).get("policy_trace") or {} for s in hyb["steps"]]
    assert traces[0]["source"] == "fsm" and traces[0]["failure"] == "bootstrap"
    routed = [t for t in traces[1:] if t]
    assert routed, "no routed decisions recorded"
    for t in routed:
        assert t["source"] == "fsm", t
        assert t["failure"] == "both_model_paths_unavailable", t
        assert t["escalated"] is True, t
    print(json.dumps({"verdict": "B2_DEGRADED_HYBRID",
                      "fast_arm": "unavailable",
                      "fsm_status": "PASS", "hybrid_status": "PASS",
                      "hybrid_sources": {"fsm": len(routed)},
                      "note": "fast and slow proposals both unavailable; router fell back to FSM"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
