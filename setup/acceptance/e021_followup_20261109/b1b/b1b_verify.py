#!/usr/bin/env python3
"""B1-B: a new episode records the initial world state it started from."""
import hashlib
import json
from pathlib import Path

EXPECTED_SHA256 = "fa084018e754798a08ece901fd4f2e1b6c5cb40edd374536e0a8fc08d2cd33a5"


def main():
    here = Path(__file__).parent
    episode = json.loads((here / "episode.json").read_text(encoding="utf-8"))
    result = json.loads((here / "result.json").read_text(encoding="utf-8"))
    state = episode.get("initial_world_state")
    assert state, "initial_world_state is empty"
    assert hashlib.sha256(state.encode()).hexdigest() == EXPECTED_SHA256
    first = next((s["policy_input"].get("world_state_canonical")
                  for s in episode["steps"]
                  if (s.get("policy_input") or {}).get("world_state_canonical")), None)
    assert state == first, "initial_world_state is not the first observed state"
    assert result["status"] == "PASS"
    assert result["task"]["outcome"] == "OUTCOME_SUCCEEDED"
    print(json.dumps({"verdict": "B1B_INITIAL_WORLD_STATE_PRESENT",
                      "sha256": EXPECTED_SHA256,
                      "chars": len(state), "steps": len(episode["steps"]),
                      "run_status": result["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
