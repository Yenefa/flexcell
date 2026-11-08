#!/usr/bin/env python3
"""C4: dual-object FSM vs MTC, three runs per arm (frozen protocol)."""
import hashlib
import json
from pathlib import Path

RUNS = [
    ('legacy-a', 'e0d42f9ebcb26c4a2165c0984e0f4d6e9dbdf157693e150fd2f39b0d3877d2f9', 'fsm', 28.564),
    ('mtc-b', 'd016ed2be84f5871ed8caa9c66c8bc2ecc1acf3f62d98dd0be4383dce92ee1b2', 'mtc', 33.327),
    ('mtc-c', 'bf23e83fb50ea70219fa43ff726093a0fb8ac74d530c87437c64eaf46ca34b59', 'mtc', 33.635),
    ('legacy-d', '7f61631af23ecf4ee89bddfe07a860ae32cd4d2487e50257c5af04055466728a', 'fsm', 28.518),
    ('legacy-e', 'cb2e9ade0688e805de26c5e8ee19ffdf950335456d34e0c2f634654bbe0f41c7', 'fsm', 28.566),
    ('mtc-f', '2aff94fa5a8071ed39946acccda7ad05586d348bd48e81c370dfaf24b4a11ac5', 'mtc', 36.143),
]


def main():
    here = Path(__file__).parent
    for rel, expected, arm, wall in RUNS:
        data = (here / rel / "result.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
        doc = json.loads(data.decode())
        assert doc["status"] == "PASS" and doc["task"]["outcome"] == "OUTCOME_SUCCEEDED", rel
        assert abs(doc["task"]["wall_seconds"] - wall) < 1e-6, rel
        trace = doc["task"]["fsm_trace"]
        assert len(trace) == 6, (rel, trace)
        assert trace[0].startswith("PICK_A") and trace[3].startswith("PICK_B"), (rel, trace)
    agg = json.loads((here / "aggregate.json").read_text())
    assert agg["fsm"]["success"] == 3 and agg["mtc"]["success"] == 3
    print(json.dumps({"verdict": "C4_BOTH_ARMS_PASS",
                      "fsm_mean_wall": agg["fsm"]["mean_wall"],
                      "mtc_mean_wall": agg["mtc"]["mean_wall"],
                      "delta_wall_s": agg["delta_wall_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
