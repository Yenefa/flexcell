#!/usr/bin/env python3
"""Verify this receipt's exact file set and bytes; never run a robot."""

import hashlib
import json
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'SHA256SUMS.json').read_text())
    actual = {str(p.relative_to(root)): p for p in root.rglob('*') if p.is_file()
              and p.name != 'SHA256SUMS.json' and '__pycache__' not in p.parts}
    problems = []
    if set(actual) != set(manifest):
        problems.append('file-set mismatch')
    for name, entry in manifest.items():
        if name not in actual:
            problems.append('missing: ' + name)
            continue
        raw = actual[name].read_bytes()
        if len(raw) != entry['bytes'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
            problems.append('bytes changed: ' + name)
    print(json.dumps(dict(ok=not problems, files=len(manifest), problems=problems)))
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
