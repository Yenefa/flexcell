#!/usr/bin/env python3
"""C8: strict 2 cm tolerance on dual_object, FSM vs MTC."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = [
    ('legacy-a', 'c0f645e03f3742cb93fa2054a99f617660b5e93482eafb49088f027391ba5bc6', 'fsm', 'PASS', 28.149),
    ('mtc-b', '8ef7c5ca7ddd3c34dce15aab045eb1f954572f8481d81362632d8fd836a48ff3', 'mtc', 'ROBOT_FAILURE', 54.436),
    ('mtc-c', 'db72de510f0df139d82cff486ffee4d39de54e2d82376f0225dc698ce4345f52', 'mtc', 'PASS', 41.911),
    ('legacy-d', 'cf23d6b6e832780fdb8887c30d22bafbf7362a207525d94d589b6722112c48eb', 'fsm', 'PASS', 28.89),
    ('legacy-e', '77cb27fa6f02d75c28e6bdfb36c1dd15f1a5009b720f5006e6be87126cc4c31b', 'fsm', 'PASS', 27.931),
    ('mtc-f', '561b0572872aae20dadc7c015b9e901198b9b624d1aa3de601fe5114a94ce20e', 'mtc', 'ROBOT_FAILURE', 54.399),
]


def main():
    agg = json.loads((HERE / "aggregate.json").read_text())
    assert agg["tolerance_m"] == 0.02
    for rel, expected, arm, status, wall in RUNS:
        data = (HERE / rel / "result.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
        doc = json.loads(data.decode())
        assert doc["status"] == status, rel
        assert abs(doc["task"]["wall_seconds"] - wall) < 1e-6, rel
    assert agg["fsm"]["success"] == 3, agg["fsm"]
    assert agg["mtc"]["success"] == 1, agg["mtc"]
    fails = [r for r in agg["rows"] if r["status"] != "PASS"]
    assert len(fails) == 2 and all(r["arm"] == "mtc" for r in fails)
    print(json.dumps({"verdict": "C8_ASYMMETRY_RECORDED",
                      "fsm_success": "3/3", "mtc_success": "1/3",
                      "fsm_mean_wall": agg["fsm"]["mean"], "mtc_mean_wall": agg["mtc"]["mean"],
                      "failures": [{"run": r["run"], "error": r["error"]} for r in fails],
                      "note": "n=3 exploratory; no significance claim"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
