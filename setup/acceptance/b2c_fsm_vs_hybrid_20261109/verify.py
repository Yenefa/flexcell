#!/usr/bin/env python3
"""B2c: FSM vs calibrated hybrid, same conditions, three runs per arm."""
import hashlib
import json
from pathlib import Path

RUNS = [
    ('fsm-a', '384166eb240d26e72d08388de416ccc4523f29f54a10162b81569cd91ebccc28', 'fsm', 14.542),
    ('hybrid-b', '01f8c6837c745f844460ca8bce473294bf14be46ddf19cce1b8a8e054f1c944f', 'hybrid', 18.097),
    ('hybrid-c', 'a8796cfa6ab93a0bd7ee0ea836534dd9b094eea5f893e7c2de54ebb7ebc11f0b', 'hybrid', 17.726),
    ('fsm-d', 'b1e454022383ac3d411121a835bfa649a1ba939799893fd6232185f5621a1647', 'fsm', 14.133),
    ('fsm-e', 'c9c8c993492238d8b4ad73dd00084c6415ab30786d9311f15ca0a5fee3bdebe3', 'fsm', 13.98),
    ('hybrid-f', 'e4534474f4b7a6f85f12a9a801b27e806d6924a9226eeaed4c4b2248f2098d63', 'hybrid', 17.134),
]


def main():
    here = Path(__file__).parent
    summary = []
    for rel, expected, arm, wall in RUNS:
        data = (here / rel / "result.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
        doc = json.loads(data.decode())
        assert doc["status"] == "PASS" and doc["task"]["outcome"] == "OUTCOME_SUCCEEDED", rel
        assert abs(doc["task"]["wall_seconds"] - wall) < 1e-6, rel
        episode = json.loads((here / rel / "episode.json").read_text())
        sources = [((s.get("policy_output") or {}).get("policy_trace") or {}).get("source") for s in episode["steps"]]
        if arm == "hybrid":
            assert sources[0] == "fsm" and sources[1:] == ["jev"] * (len(sources) - 1), (rel, sources)
        else:
            assert all(src is None for src in sources), (rel, sources)
        summary.append({"run": rel, "arm": arm, "wall_s": wall})
    agg = json.loads((here / "aggregate.json").read_text())
    assert agg["fsm"]["success"] == 3 and agg["hybrid"]["success"] == 3
    assert agg["hybrid"]["fast_decisions"] == 9 and agg["hybrid"]["escalations"] == 0
    print(json.dumps({"verdict": "B2C_BOTH_ARMS_PASS",
                      "fsm_mean_wall": agg["fsm"]["mean_wall"],
                      "hybrid_mean_wall": agg["hybrid"]["mean_wall"],
                      "delta_wall_s": agg["delta_wall_s"],
                      "fast_hit_rate": agg["hybrid"]["fast_decisions"] / agg["hybrid"]["routed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
