#!/usr/bin/env python3
"""B2b: hybrid routing with a real calibrated fast arm on one real Gazebo run."""
import hashlib
import json
from pathlib import Path

HASHES = {
    'b2b-run/result.json': '24db3ba023462de88627fa4bd5dcaa500e38c02f1392821d0c5dcc290ef23064',
    'b2b-run/episode.json': 'c0e69d89164e9b3ab6a9028011367895bbd628e1b780b3642ef7718ee2cb1728',
    'calibration-n51.json': 'd20e6e7df8739c9d7f8ff4783e5d6ffc8206c2f376583e2416d12d8bca08c422',
}


def main():
    here = Path(__file__).parent
    for rel, expected in HASHES.items():
        data = (here / rel).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, rel + " drifted"
    result = json.loads((here / "b2b-run/result.json").read_text())
    episode = json.loads((here / "b2b-run/episode.json").read_text())
    cal = json.loads((here / "calibration-n51.json").read_text())
    assert result["status"] == "PASS" and result["task"]["outcome"] == "OUTCOME_SUCCEEDED"
    assert cal["label_definition"] == "FSM_ACTION_AGREEMENT"
    assert cal["model"] == "deepseek-flash"
    assert cal["model_sha256_kind"].startswith("remote_identity")
    bins = [b for b in cal["bins"] if b["n"] and b["wilson_lower"] >= 0.85]
    assert bins, "no calibration bin clears the frozen threshold"
    rows = [((s.get("policy_output") or {}).get("policy_trace") or {}) for s in episode["steps"]]
    assert rows[0]["source"] == "fsm" and rows[0]["failure"] == "bootstrap"
    fast = [t for t in rows[1:] if t]
    assert len(fast) == 3, fast
    for t in fast:
        assert t["source"] == "jev", t
        assert t["escalated"] is False and t.get("failure") is None, t
        assert t["fast_confidence_calibrated"] is True, t
        assert t["threshold"] == 0.85
    print(json.dumps({"verdict": "B2B_FAST_ARM_ROUTED",
                      "fast_decisions": len(fast),
                      "fast_arm": "deepseek-flash (calibrated sha %s...)" % cal["model_sha256"][:8],
                      "task_wall_s": result["task"]["wall_seconds"],
                      "note": "n=1 run; no success-rate comparison yet"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
