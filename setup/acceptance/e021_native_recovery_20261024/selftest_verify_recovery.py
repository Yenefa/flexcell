#!/usr/bin/env python3
"""Adversarial self-test for verify_recovery.py.

A verifier that always prints VERIFIED proves nothing. This script copies the
archive into a throwaway tree and checks that the verifier actually fails on
every kind of drift it claims to catch: a flipped byte, a deleted file, an
unlisted file, a tampered batch, and a manifest reference set that no longer
matches the frozen inventory.

    python3 setup/acceptance/e021_native_recovery_20261024/selftest_verify_recovery.py

Standard library only, no network, no ROS. Exit 0 if all cases behave as
specified, 1 otherwise.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEIGHBOURS = ["e021_native_recovery_20261024", "fixed_smoke_window_20261024", "tau_sweep_desktop_20261005"]


def stage(root: Path) -> Path:
    accept = root / "setup" / "acceptance"
    accept.mkdir(parents=True)
    for name in NEIGHBOURS:
        shutil.copytree(HERE.parent / name, accept / name)
    return accept


def run(verifier: Path) -> tuple[int, str]:
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "ROS_DISTRO", "AMENT_PREFIX_PATH")}
    proc = subprocess.run(
        [sys.executable, str(verifier)],
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    results: list[tuple[str, bool, str]] = []

    with tempfile.TemporaryDirectory() as tmp:
        accept = stage(Path(tmp))
        verifier = accept / "e021_native_recovery_20261024" / "verify_recovery.py"
        episode_dir = accept / "e021_native_recovery_20261024" / "episodes"
        one = sorted(episode_dir.glob("*.json"))[0]
        pristine = one.read_bytes()

        code, out = run(verifier)
        results.append(("A clean archive verifies", code == 0 and "VERIFIED" in out, f"exit={code}"))

        one.write_bytes(pristine[:100] + bytes([pristine[100] ^ 0x01]) + pristine[101:])
        code, out = run(verifier)
        results.append(("B one flipped byte rejected", code == 1 and "sha mismatch" in out, f"exit={code}"))
        one.write_bytes(pristine)

        one.unlink()
        code, out = run(verifier)
        results.append(("C deleted episode rejected", code == 1 and "absent" in out, f"exit={code}"))
        one.write_bytes(pristine)

        planted = episode_dir / "planted.json"
        planted.write_bytes(pristine)
        code, out = run(verifier)
        results.append(("D unlisted episode rejected", code == 1 and "unlisted" in out, f"exit={code}"))
        planted.unlink()

        batch = accept / "tau_sweep_desktop_20261005" / "batch_20261005_161922.jsonl"
        original = batch.read_bytes()
        batch.write_bytes(original.replace(b'"SUCCEEDED"', b'"FAILED"', 1))
        code, out = run(verifier)
        results.append(("E tampered batch rejected", code == 1 and "sha mismatch" in out, f"exit={code}"))
        batch.write_bytes(original)

        manifest_path = accept / "e021_native_recovery_20261024" / "recovery_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        victim = next(k for k, v in manifest["episodes"].items() if v.get("status") == "PRESENT")
        manifest["episodes"][victim]["status"] = "MISSING"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        code, out = run(verifier)
        results.append(("F reference set shrink detected", code == 1 and "differs from frozen" in out, f"exit={code}"))

    width = max(len(name) for name, _, _ in results)
    failed = 0
    for name, good, detail in results:
        print(f"  {name.ljust(width)}  {'PASS' if good else 'FAIL'}  ({detail})")
        failed += 0 if good else 1
    print(f"\n{len(results) - failed}/{len(results)} cases behave as specified")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
