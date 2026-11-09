#!/usr/bin/env python3
"""C5: recovery_once FSM vs MTC, three runs per arm."""
import hashlib
import json
from pathlib import Path

RUNS = [
    ('legacy-a', '1c77fde09d3c5aa215172b6757edacabef25d6d809a3a374d2c831e85aea2774', 'fsm', 14.218),
    ('mtc-b', 'ab3c9ea75d7db17944fb9fe15e2b542a9593d51581ad692a21b2a32bc462cc6b', 'mtc', 16.341),
    ('mtc-c', 'd2e28d333fcb471ff2f11dd1460b3220e1f3a85ff4166a3977d17c6d756f9dba', 'mtc', 16.326),
    ('legacy-d', '1b42a4bdaf9d66af2dd9e428b419346ec9a14238e44a42ac5ce5a2eb4c86e07d', 'fsm', 14.214),
    ('legacy-e', 'ebbd0ca81efac3cdb13d9b9f4ed23511f2e3e72c8a80d98c99f2020f117563de', 'fsm', 14.369),
    ('mtc-f', '108f958440db68f17a6ae99ce8278671e0787c8c123ae5c75478b878c24ccb4f', 'mtc', 16.323),
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
        assert trace[0].startswith("PICK_A(attempt=1):FAIL"), (rel, trace)
        assert trace[1].startswith("RECOVERY:REOBSERVE+RETRY"), (rel, trace)
    agg = json.loads((here / "aggregate.json").read_text())
    assert agg["fsm"]["success"] == 3 and agg["mtc"]["success"] == 3
    print(json.dumps({"verdict": "C5_BOTH_ARMS_PASS",
                      "fsm_mean_wall": agg["fsm"]["mean_wall"],
                      "mtc_mean_wall": agg["mtc"]["mean_wall"],
                      "delta_wall_s": agg["delta_wall_s"],
                      "recoveries_per_run": agg["fsm"]["recoveries"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
