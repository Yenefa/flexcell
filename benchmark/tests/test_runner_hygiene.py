#!/usr/bin/env python3
"""Forbid the class of defect that silently disabled two pipeline steps.

WHAT HAPPENED TWICE: a batch runner cd-ed into the simulator checkout to launch Gazebo and
then invoked a helper by RELATIVE path, e.g. "python3 runtime/recovery/recovery_driver.py".
The call failed, the step never ran, and the batch still produced plausible numbers:
  - the self-assessment never ran, so every claim defaulted to False;
  - the recovery driver never ran, so "arm R" was arm B relabelled.
I fixed each call I could see, and the next copy of the script reproduced the same trap.

The rule is now mechanical: the ACTIVE runner must address every helper absolutely under
$W, so cwd cannot matter. Superseded copies are deliberately left untouched.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNNER_DIR = ROOT.parent / "ci-public-window" / "scripts"
HELPER_HINTS = ("runtime/", "benchmark/", "experiments/", "evolution/")


def is_superseded(path):
    if not path.exists():
        return True
    head = "\n".join(path.read_text(encoding="utf-8").splitlines()[:10])
    return "SUPERSEDED" in head


def active_runners():
    """Only runners still in use.

    Superseded copies are ARCHAEOLOGY: they are the record of what actually ran, so their
    relative-path calls must NOT be repaired - editing them would falsify the evidence of
    the very defect this test exists for. They must carry a SUPERSEDED banner instead.
    """
    if not RUNNER_DIR.is_dir():
        return []
    cand = sorted(p for p in RUNNER_DIR.glob("*.sh")
                  if p.name.startswith(("run_batch", "evobot_pair", "evobot_rerun")))
    return [p for p in cand if not is_superseded(p)]


def test_no_active_runner_calls_a_helper_through_a_relative_path():
    offenders = []
    for path in active_runners():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if s.startswith("#") or "python3" not in s:
                continue
            for m in re.finditer(r"python3\s+(\S+)", s):
                target = m.group(1)
                if not any(h in target for h in HELPER_HINTS):
                    continue
                absolute = (target.startswith('"$W/') or target.startswith("$W/")
                            or target.startswith("/"))
                if not absolute:
                    offenders.append("%s:%d: %s" % (path.name, n, s[:100]))
    assert not offenders, "relative helper invocation(s) found:\n" + "\n".join(offenders)


def test_the_unified_runner_exists_and_validates_the_batch():
    run = RUNNER_DIR / "run_batch.sh"
    assert run.exists(), "run_batch.sh is the single runner now"
    src = run.read_text(encoding="utf-8")
    assert "validate_batch.py" in src
    assert "BATCH_REJECTED" in src
    assert "RECOVERY_DID_NOT_RUN" in src


def test_the_unified_runner_declares_its_helpers_absolutely():
    src = (RUNNER_DIR / "run_batch.sh").read_text(encoding="utf-8")
    for name in ("PLAN_B", "CLIENT", "CAPTURE", "OBSERVE", "SEALED",
                 "RECOVERY", "ASSESS", "VALIDATE"):
        assert re.search(r'^%s="\$W/' % name, src, re.M), name


def test_superseded_runners_keep_the_defect_as_evidence():
    """Repairing them would destroy the record of what actually ran."""
    kept = 0
    for old in ("evobot_pair48.sh", "evobot_rerun3.sh"):
        p = RUNNER_DIR / old
        if not p.exists():
            continue
        src = p.read_text(encoding="utf-8")
        assert "SUPERSEDED" in src, old
        assert "python3 runtime/recovery/recovery_driver.py" in src, (
            old + ": the historical relative-path call was edited away")
        kept += 1
    assert kept >= 1
