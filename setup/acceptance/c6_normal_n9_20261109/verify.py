#!/usr/bin/env python3
"""C6: normal-scenario substrate comparison at nine runs per arm."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
C3 = ROOT / "setup" / "acceptance" / "c3_fsm_vs_mtc_20261109"
HERE = Path(__file__).parent

RUNS = [
    ('C3', 'legacy-a', '4e86ae44b2322472e6a150164b99dac89bf4709a0387a5df946b356d1500d7cb', 'fsm', 14.671),
    ('C3', 'mtc-b', '6209ce33296138baf696fcd7d8314066347716ca6a8c39f1c9f1507fa8b390e1', 'mtc', 16.771),
    ('C3', 'mtc-c', '3c804037f70fa23a1dc4fa76da2d75a4f07c99b085d97a27bf8a92a3e239254e', 'mtc', 16.6),
    ('C3', 'legacy-d', '424b2c245b1c5549b9f0b235190227b0da0f5f086813928b44cfc0a4490b4bbd', 'fsm', 17.853),
    ('C3', 'legacy-e', '59f8a9f53e80469c42b0f08b28d6d1b77d3e66d0f9ca00e72e55c5fb36cc2620', 'fsm', 14.588),
    ('C3', 'mtc-f', '5c29a0ff849d4fd304e07c4fe3644ef36ef026f8fdf4a5489da74e92d2c44c7b', 'mtc', 24.52),
    ('C6', 'legacy-a', 'f7720c07408a7d78fe40f2dd5b0c744d46befa8f0a9e07e81164117c05516177', 'fsm', 14.271),
    ('C6', 'mtc-b', '747971759b2c5da5f80e4f009fb34fdf09d75c914896bce731d227893f7a4a57', 'mtc', 16.281),
    ('C6', 'mtc-c', '878366a14eabcf019c3bf9f77b99f4924b85be21e289ca83a4909b3793f8d482', 'mtc', 16.541),
    ('C6', 'legacy-d', '7e7799268c8b4f97caa4601099b26960039e29ddb818bd51a7054239b8e5761d', 'fsm', 14.019),
    ('C6', 'mtc-e', '50192ebc212cdc977f07f976506b1d4a2a2573c94269f78865399bdb2a4813ba', 'mtc', 15.927),
    ('C6', 'legacy-f', '775965dec6e03bcf100015ab88b881c3a47734e271aef7a4f2bc9e75b12fe465', 'fsm', 14.12),
    ('C6', 'mtc-g', 'ccf6930bfcb7a90be2edd69198b3f0f0245da406240b258b7b85603a861e9331', 'mtc', 16.023),
    ('C6', 'legacy-h', '03e1cd206a6cbf044ee2c0c80e5197258cdd3cbfbf3711bec0abf319a7ac764d', 'fsm', 14.173),
    ('C6', 'legacy-i', '7c4bd5d80de9e124facfa7590b1663d08937b2c53fc7c376adb3f96589e60324', 'fsm', 14.069),
    ('C6', 'mtc-j', '8b7746777a0bc8f5590d9e2ff57e44939be0c2136a57e797b2a974eeb8de10c9', 'mtc', 15.824),
    ('C6', 'legacy-k', '5bc1236692dfc884e2ee361c598d4c597b66101a0fba398d8a67955e89428a6b', 'fsm', 14.219),
    ('C6', 'mtc-l', 'b7d8c5fc172c234bb0a40c3442036bb93ebad364afaefefce638af35fef8da07', 'mtc', 15.821),
]


def main():
    walls = {"fsm": [], "mtc": []}
    for phase, rel, expected, arm, wall in RUNS:
        path = (HERE / rel / "result.json") if phase == "C6" else (C3 / rel / "result.json")
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, str(path) + " drifted"
        doc = json.loads(data.decode())
        assert doc["status"] == "PASS", rel
        assert abs(doc["task"]["wall_seconds"] - wall) < 1e-6, rel
        walls[arm].append(wall)
    agg = json.loads((HERE / "aggregate.json").read_text())
    assert agg["n_per_arm"] == 9 and len(walls["fsm"]) == 9 and len(walls["mtc"]) == 9
    assert agg["fsm"]["success"] == 9 and agg["mtc"]["success"] == 9
    print(json.dumps({"verdict": "C6_N9_BOTH_ARMS_PASS",
                      "fsm_mean": agg["fsm"]["mean"], "mtc_mean": agg["mtc"]["mean"],
                      "delta_mean_s": agg["delta_mean_s"], "delta_median_s": agg["delta_median_s"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
