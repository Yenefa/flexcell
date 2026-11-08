"""Append-only JSONL event recorder; one run directory per attempt."""
import json
import os
import time
from pathlib import Path


class Recorder:
    def __init__(self, run_dir):
        self.dir = Path(run_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events = self.dir / "events.jsonl"
        self.started = time.monotonic()

    def emit(self, kind, **fields):
        row = {"t": round(time.monotonic() - self.started, 6), "kind": kind}
        row.update(fields)
        with self.events.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    def write_json(self, name, obj):
        (self.dir / name).write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def read_json(self, name, default=None):
        path = self.dir / name
        if not path.is_file():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
