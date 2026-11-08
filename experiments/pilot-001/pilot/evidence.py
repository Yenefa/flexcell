"""Collect required evidence and compute completeness."""
import hashlib
from pathlib import Path

REQUIRED = ("verdict.json", "telemetry/execution.log", "episode.json", "fingerprint.json")


def collect(workspace, run_dir):
    ws = Path(workspace)
    run = Path(run_dir)
    items = {}
    for rel in REQUIRED:
        src = ws / rel
        if src.is_file():
            data = src.read_bytes()
            items[rel] = {
                "present": True,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        else:
            items[rel] = {"present": False, "bytes": 0, "sha256": None}
    present = sum(1 for v in items.values() if v["present"])
    payload = {
        "items": items,
        "present": present,
        "required": len(REQUIRED),
        "completeness": round(present / float(len(REQUIRED)), 4),
    }
    (run / "evidence.json").write_text(__import__("json").dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
