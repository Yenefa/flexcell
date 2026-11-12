#!/usr/bin/env python3
"""W6: cold vs warm transfer, three runs per arm (frozen protocol)."""
import hashlib
import json
from pathlib import Path

RUNS = [
    ('cold-c1', '920fdb83b448b5e6510c58e7bff392c26e351af4b443fc930de1376caf6a76ff', 'cold', False),
    ('warm-w1', '4115288155295990e70c8b98c08bc8c83663cbdfbce0742a0de5884718deb90f', 'warm', True),
    ('warm-w2', '09fefe02b746573ccd64906c906991f2d0024300906e56f720c3a53fc397ee3e', 'warm', True),
    ('cold-c2', '9745532d0bc8b03a97b10bdc62f0ef2996163f64b9c0303f4120845dae54fff2', 'cold', False),
    ('cold-c3', '7931c67528d467e64e5c40ffe73d48c2aabf1bcdaad48535f912fb833bd3325a', 'cold', False),
    ('warm-w3', 'a4daa6d5c0541b94a237ca1e71546401966b8180fc3f0214b0e16e3800644478', 'warm', False),
]


def main():
    here = Path(__file__).parent
    for rel, expected, arm, success in RUNS:
        data = (here / rel / "result.json").read_bytes()
        _sha_ok = any(
            hashlib.sha256(v).hexdigest() == expected
            for v in (data,
                      data.replace(b"\r\n", b"\n"),
                      data.replace(b"\n", b"\r\n")))
        assert _sha_ok, rel + " drifted"
        doc = json.loads(data.decode())
        assert bool(doc["success"]) == success, rel
        if success:
            assert doc["verdict"]["status"] == "PASS", rel
    agg = json.loads((here / "aggregate.json").read_text())
    assert agg["cold"]["success"] == 0 and agg["warm"]["success"] == 2
    for row in agg["rows"]:
        if not row["success"]:
            assert row["wrote_plan"] is False or row["plan"] == [0.45, 0.0, 0.0175], row
    print(json.dumps({"verdict": "W6_N3_RECORDED", "cold_success": "0/3",
                      "warm_success": "2/3", "warm_mean_tokens": agg["warm"]["mean_tokens"],
                      "note": "n=3 exploratory, no significance claimed"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
