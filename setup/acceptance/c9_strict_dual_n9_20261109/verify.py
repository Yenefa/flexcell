#!/usr/bin/env python3
"""C9: strict 2 cm dual_object at nine runs per arm (C8 + six new per arm)."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
C8 = HERE.parent / "c8_strict_dual_20261109"
RUNS = [
    ('C8', 'legacy-a', 'c0f645e03f3742cb93fa2054a99f617660b5e93482eafb49088f027391ba5bc6', 'fsm', 'PASS', 28.149),
    ('C8', 'mtc-b', '8ef7c5ca7ddd3c34dce15aab045eb1f954572f8481d81362632d8fd836a48ff3', 'mtc', 'ROBOT_FAILURE', 54.436),
    ('C8', 'mtc-c', 'db72de510f0df139d82cff486ffee4d39de54e2d82376f0225dc698ce4345f52', 'mtc', 'PASS', 41.911),
    ('C8', 'legacy-d', 'cf23d6b6e832780fdb8887c30d22bafbf7362a207525d94d589b6722112c48eb', 'fsm', 'PASS', 28.89),
    ('C8', 'legacy-e', '77cb27fa6f02d75c28e6bdfb36c1dd15f1a5009b720f5006e6be87126cc4c31b', 'fsm', 'PASS', 27.931),
    ('C8', 'mtc-f', '561b0572872aae20dadc7c015b9e901198b9b624d1aa3de601fe5114a94ce20e', 'mtc', 'ROBOT_FAILURE', 54.399),
    ('C9', 'legacy-g', 'ef225b1ce19d67694232187df1892d1a2cf131c62c3a3bfc5aa7213d5e546efc', 'fsm', 'PASS', 28.143),
    ('C9', 'mtc-h', 'ab0d78a8d83349d440efa7c085da9d589de114ee2d0555ffee4825fe6d3af1b7', 'mtc', 'PASS', 33.299),
    ('C9', 'mtc-i', 'c70ef8bf789c921c9daaee946ec2718398107327908adc2442fdcae725f998bc', 'mtc', 'PASS', 33.05),
    ('C9', 'legacy-j', 'f8ac674ca3b60aabc3cdf2ec1081edf2661d1132b9734ddd88e65c6e1394b396', 'fsm', 'PASS', 28.386),
    ('C9', 'mtc-k', 'a575a87bf076a35e6f94fc9494036309c00741d2f4ae3fbc7594750883356a17', 'mtc', 'PASS', 33.317),
    ('C9', 'legacy-l', 'f77e41c6d4fb5e8de78aa6c23925b7a1d8c6641c026c97041c209c41a1caf606', 'fsm', 'PASS', 27.481),
    ('C9', 'mtc-m', 'c52d28abfe85aa46d362b2c64b1a3e4c829dd56a55d121ef62f83568f65bd652', 'mtc', 'ROBOT_FAILURE', 54.344),
    ('C9', 'legacy-n', 'c931fc34c6e117203a89cb8a81d318fced4b72fa95b092bbba2d2f846156637b', 'fsm', 'PASS', 28.389),
    ('C9', 'legacy-o', '7a1e5e181249ebf76c3e792701b57a842292f0d20535cf2466e3188e3e6e2cc1', 'fsm', 'PASS', 28.362),
    ('C9', 'mtc-p', '97c59e12ae21a4938068403836e25eeea91cac5e25ab2e936e8f528e1d4ee854', 'mtc', 'PASS', 32.726),
    ('C9', 'mtc-q', 'fe1f93f55bf2d87bb024597847acc6c19ea147dc961ddeeea6ab429f1d9d36da', 'mtc', 'PASS', 33.267),
    ('C9', 'legacy-r', '8d4373917eb19c1264bc9182d00874865c47d7d3560748de246fba86ba0aeb69', 'fsm', 'PASS', 28.799),
]


def main():
    agg = json.loads((HERE / "aggregate.json").read_text())
    for phase, rel, expected, arm, status, wall in RUNS:
        path = (C8 / rel / "result.json") if phase == "C8" else (HERE / rel / "result.json")
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, str(path)
        doc = json.loads(data.decode())
        assert doc["status"] == status, rel
        assert abs(doc["task"]["wall_seconds"] - wall) < 1e-6, rel
    assert agg["n_per_arm"] == 9
    assert agg["fsm"]["success"] == 9, agg["fsm"]
    assert agg["mtc"]["success"] == 6, agg["mtc"]
    fails = [r for r in agg["rows"] if r["status"] != "PASS"]
    assert len(fails) == 3 and all(r["arm"] == "mtc" for r in fails)
    print(json.dumps({"verdict": "C9_N9_ASYMMETRY", "fsm": "9/9", "mtc": "6/9",
                      "fsm_mean_wall": agg["fsm"]["mean"], "mtc_mean_wall": agg["mtc"]["mean"],
                      "failures": [{"run": r["run"], "error": r["error"]} for r in fails]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
