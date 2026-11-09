#!/usr/bin/env python3
"""Offline replay of the W5 self-improvement evidence (no API key, no Gazebo).

Reads the recorded runs and prints the closed loop: dirty config -> agent edits ->
target gate -> regression gate. Exits non-zero if any recorded verdict is not PASS,
so the demo is also a check.
"""
import hashlib
import json
import sys
from pathlib import Path

RUNS = Path(__file__).resolve().parents[1] / "runs"

CASES = [
    ("W5-E2b (single regression, 3/3)", RUNS / "p1.5-w5e2b-20261109", ["rep1", "rep2", "rep3"]),
    ("W5-E2d (multi regression, explicit action)", RUNS / "p1.5-w5e2d-20261109", ["rep1", "rep2"]),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def main():
    failures = 0
    for label, base, reps in CASES:
        print("=" * 72)
        print(label)
        for rep in reps:
            result_path = base / rep / "result.json"
            verdict_path = base / rep / "verdict.json"
            if not result_path.is_file():
                print("  %-6s MISSING %s" % (rep, result_path))
                failures += 1
                continue
            result = json.loads(result_path.read_text())
            verdict = json.loads(verdict_path.read_text())
            config = (base / rep / "week1.yaml").read_text() if (base / rep / "week1.yaml").is_file() else ""
            zone = [line.strip() for line in config.splitlines() if line.strip().startswith("zone_2_x")]
            gates = {k: v.get("status") for k, v in verdict.items() if isinstance(v, dict) and "status" in v}
            ok = result.get("success") is True and verdict.get("passed") is True
            failures += 0 if ok else 1
            print("  %-6s success=%-5s iters=%-2s tokens=%-5s %s"
                  % (rep, result.get("success"), result.get("iterations"),
                     (result.get("cost") or {}).get("tokens"), zone))
            print("         gates=%s  passed=%s  sha(result)=%s"
                  % (gates, verdict.get("passed"), digest(result_path)))
    print("=" * 72)
    if failures:
        print("REPLAY FAILED: %d recorded verdict(s) not PASS" % failures)
        return 1
    print("REPLAY OK: every recorded run has an independent PASS verdict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
