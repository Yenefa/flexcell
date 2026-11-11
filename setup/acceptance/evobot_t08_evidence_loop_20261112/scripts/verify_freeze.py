#!/usr/bin/env python3
"""Re-check the frozen fingerprint after arm U. Any drift is a hard failure.

This exists because "I did not change anything after U" is a claim, and a claim
is not evidence. If a covered file changed between the freeze and this check, the
U measurements no longer belong to the frozen policy and must be reported as
NOT_FROZEN rather than as an unseen result.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def sha256(path):
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv):
    freeze_path = Path(argv[1]) if len(argv) > 1 else HERE / "evidence" / "policy_freeze.json"
    frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
    drifted = []
    for path, expected in sorted(frozen["files"].items()):
        p = Path(path)
        if not p.is_file():
            drifted.append((path, expected, "MISSING"))
            continue
        actual = sha256(p)
        if actual != expected:
            drifted.append((path, expected, actual))
    if drifted:
        print("FREEZE_VIOLATED (%d)" % len(drifted))
        for path, expected, actual in drifted:
            print("  %s\n    expected %s\n    actual   %s" % (path, expected, actual))
        return 1
    print("FREEZE_OK -- all %d covered files match the pre-U fingerprint"
          % len(frozen["files"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
