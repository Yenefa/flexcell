#!/usr/bin/env python3
"""Summarise a W5 transcript: reads, first write, iterations, tokens, verdict."""
import json, sys
from pathlib import Path

def main(run_dir):
    run = Path(run_dir)
    events = [json.loads(l) for l in (run / "events.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    iters = [e for e in events if e.get("kind") == "iteration"]
    calls = [c for i in iters for c in i.get("calls", [])]
    counts = {}
    for name, *_ in calls:
        counts[name] = counts.get(name, 0) + 1
    first_write = None
    for idx, it in enumerate(iters, 1):
        if any(name in ("write_file", "edit_file") for name, *_ in it.get("calls", [])):
            first_write = idx
            break
    result = json.loads((run / "result.json").read_text(encoding="utf-8"))
    verdict = json.loads((run / "verdict.json").read_text(encoding="utf-8"))
    out = {"run": str(run), "success": result.get("success"), "iterations": result.get("iterations"),
           "tokens": (result.get("cost") or {}).get("tokens"), "tool_calls": counts,
           "first_write_iteration": first_write, "verdict_passed": verdict.get("passed"),
           "gates": {k: v.get("status") for k, v in verdict.items() if isinstance(v, dict) and "status" in v}}
    print(json.dumps(out, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
