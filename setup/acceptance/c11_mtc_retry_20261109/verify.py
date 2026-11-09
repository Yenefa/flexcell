#!/usr/bin/env python3
"""C11: MTC planning-retry evaluation over twelve real runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).parent
RUNS = [
    ('mtc-a', 'a201a7782414b795b3612562bebb05bb52a5cb5126021383b4d4d4f513110ff0', 'mtc', 'strict', 'PASS', 34.402),
    ('mtc-b', '962007ff95de1a8cd76834438b0e75261f810c4b728bd1dbb36dd79657476154', 'mtc', 'strict', 'PASS', 34.414),
    ('legacy-c', '9be1609e93fe97558dea44c169570d37b7787540ed5bb399b01dc7526d67e6c4', 'legacy', 'strict', 'PASS', 29.224),
    ('mtc-d', '56eeb73fe5c205a85a70ae6aa55c4b29be27180846a881be402413dd72740843', 'mtc', 'strict', 'PASS', 34.516),
    ('legacy-e', 'a49c80bfec46394987b2c73f42d5161ae07e0d40f443b9ec1f18c8376d34b061', 'legacy', 'strict', 'PASS', 28.887),
    ('mtc-f', '06b259eea74dced5a613ba2cfe14deae682ae5fcdc4bbac85aa307046f5fd583', 'mtc', 'strict', 'PASS', 35.435),
    ('mtc-g', 'cc63a94a72127c20fa9d3d9f81c41fd8acf3bef7f51c288193e518f89a399dcb', 'mtc', 'strict', 'PASS', 35.96),
    ('legacy-h', 'e4d08e9b8ca1962d1c5c416b309afb060af68dbc00101ee300a66d839bcee668', 'legacy', 'strict', 'PASS', 29.25),
    ('mtc-i', 'b179db067fbafebce02ca8e8a7b19bf1b882c972af0dd59352a403e8b5f30124', 'mtc', 'default', 'PASS', 34.376),
    ('mtc-j', 'c653b2127fe8b53264bafb750a2c26ee9490fdc309f153c34c6858aab7bcf8d8', 'mtc', 'default', 'PASS', 34.309),
    ('mtc-k', 'a6b492d9e2d0d12cbd9786b6b64d721d3c86a17f69ae02ee30a8225d8e48cb5e', 'mtc', 'default', 'PASS', 33.263),
    ('mtc-l', '07da3f4b7cf8880d329e1891ecc5659e2152b99707042f8313b288f306400172', 'mtc', 'default', 'PASS', 33.334),
]


def main():
    agg = json.loads((HERE / "aggregate.json").read_text())
    for rel, expected, arm, mode, status, wall in RUNS:
        data = (HERE / rel / "result.json").read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
        doc = json.loads(data.decode())
        assert doc["status"] == status == "PASS", rel
        assert abs(doc["task"]["wall_seconds"] - wall) < 1e-6, rel
    assert agg["strict_mtc"]["success"] == agg["strict_mtc"]["n"] == 5
    assert agg["strict_fsm"]["success"] == agg["strict_fsm"]["n"] == 3
    assert agg["default_mtc"]["success"] == agg["default_mtc"]["n"] == 4
    print(json.dumps({"verdict": "C11_NO_REGRESSION_TARGET_5OF5",
                      "strict_mtc": "5/5 (pre-fix 6/9)", "strict_fsm": "3/3", "default_mtc": "4/4",
                      "note": "pre-registered target was 6 runs; five were scheduled (documented deviation)"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
