#!/usr/bin/env python3
"""C7: strict 2 cm tolerance, FSM vs MTC, three runs per arm."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = [
    ('legacy-a', '3cfa47b1d135345e2b1bd536926ed9b15a403e031c53581fac3fcf66f00f9ff8', 'fsm', 13.965),
    ('mtc-b', 'd442b81f866d6b0a83466e8da191932fd383410a0c9997e1f8c97cf199871e1d', 'mtc', 15.923),
    ('mtc-c', '0d921cf485aa65d1952b4db0978f3f11b47eb9fadbe9a67c7aee9a8adfaad82a', 'mtc', 15.87),
    ('legacy-d', 'd4b0ba9ae55a272a779af567b00bf5a0f0880cb35e90ed77655d98b59ea1dbee', 'fsm', 14.02),
    ('legacy-e', '9d3e10edb3f0e166be3d443eede053b68e05487d2b19b77fc578483cd3af9931', 'fsm', 14.319),
    ('mtc-f', 'bb4c006cedcbd7237f07c47e49464ba676fde04a65d137efd9638ff653e2ee62', 'mtc', 17.526),
]


def main():
    agg = json.loads((HERE / "aggregate.json").read_text())
    assert agg["tolerance_m"] == 0.02
    prints = {"fsm": [], "mtc": []}
    for rel, expected, arm, wall in RUNS:
        data = (HERE / rel / "result.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
        doc = json.loads(data.decode())
        assert doc["status"] == "PASS", rel
        assert abs(doc["task"]["wall_seconds"] - wall) < 1e-6, rel
        prints[arm].append(doc["runtime_fingerprint"])
    assert agg["fsm"]["success"] == 3 and agg["mtc"]["success"] == 3
    print(json.dumps({"verdict": "C7_BOTH_ARMS_PASS_AT_2CM",
                      "fsm_mean_wall": agg["fsm"]["mean"], "mtc_mean_wall": agg["mtc"]["mean"],
                      "delta_wall_s": agg["delta_mean_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
