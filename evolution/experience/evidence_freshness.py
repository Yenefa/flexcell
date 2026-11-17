#!/usr/bin/env python3
"""Is the committed evidence still what the code produces?

THE DEFECT THIS EXISTS FOR
    setup/acceptance/evobot_continual_chain_20261118/ holds a committed run: 32 json files
    and the store/ledger they describe. verify.py regenerates it into a temp directory and
    asserts properties of THAT run - so it is a check that the code is self-consistent, not
    that the committed evidence still describes the code.

    They had already diverged. The entry ids in the committed artifacts come from before a
    schema field was added, so 18 of 32 files recorded a chain the current code does not
    produce. The committed evidence was internally consistent and externally stale, and
    nothing said so - a reader would take it as "this is what the code does".

WHY IT COMPARES NUMBERS AND NOT BYTES
    Entry ids are digests of the entry body, so adding a field renames every id downstream.
    A byte comparison would fail on every harmless schema addition and would be switched off
    within a week - which is how a gate stops existing. What a reader actually quotes is the
    NUMBERS: how many entries, how many instances fixed, what the hit rate is, how many
    routings carry. Those must not drift silently. Id churn is reported separately, as
    information rather than as failure, because it is a fact about the evidence's age.
"""
import json
import os
import re
import subprocess
import sys
import tempfile

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EVIDENCE = os.path.join(WT, "setup", "acceptance", "evobot_continual_chain_20261118")
DEMO = os.path.join(WT, "evolution", "experience", "demo_continual.py")

# Fields that are identity, not measurement. Excluded from the number comparison.
_IDENTITY = re.compile(r"(_id|_sha256|_by|_ref|_from|ran_at)$")

# Files the demo does not produce: they come from other steps or from verify.py itself.
_NOT_FROM_THE_DEMO = ("review_artifact_", "verify_result.json")


def _numbers(obj, path=""):
    """Every numeric leaf, keyed by its path. Booleans are not numbers here."""
    out = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if _IDENTITY.search(str(key)):
                continue
            out.update(_numbers(value, path + "/" + str(key)))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            out.update(_numbers(value, "%s[%d]" % (path, i)))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out[path] = obj
    return out


def _ids(obj):
    """Every digest-shaped string, for the separate age report."""
    found = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            found |= _ids(value)
    elif isinstance(obj, list):
        for value in obj:
            found |= _ids(value)
    elif isinstance(obj, str):
        found |= set(re.findall(r"\b[0-9a-f]{64}\b", obj))
    return found


def regenerate(dest=None):
    """Run the demo into a fresh directory and return that directory."""
    dest = dest or tempfile.mkdtemp(prefix="evidence_")
    proc = subprocess.run([sys.executable, DEMO, "--out", dest], cwd=WT,
                          capture_output=True, text=True, timeout=900)
    if proc.returncode:
        raise RuntimeError("the demo failed to run: " + (proc.stderr or "")[-400:])
    return dest


def compare(fresh_dir=None, evidence=None):
    """Compare the committed evidence against a freshly generated run.

    Returns {"number_drift": [...], "id_churn": [...], "missing": [...],
             "unchanged_numbers": n, "claim": str}.
    """
    evidence = evidence or EVIDENCE
    fresh = fresh_dir or regenerate()
    number_drift, id_churn, missing, identical = [], [], [], 0
    for name in sorted(os.listdir(evidence)):
        if not name.endswith(".json") or name.startswith(_NOT_FROM_THE_DEMO):
            continue
        old_path = os.path.join(evidence, name)
        new_path = os.path.join(fresh, name)
        if not os.path.exists(new_path):
            missing.append({"file": name, "why": "the demo no longer produces it"})
            continue
        try:
            old = json.load(open(old_path, encoding="utf-8"))
            new = json.load(open(new_path, encoding="utf-8"))
        except (OSError, ValueError) as exc:
            missing.append({"file": name, "why": "unreadable: %s" % exc})
            continue
        a, b = _numbers(old), _numbers(new)
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                number_drift.append({"file": name, "field": key,
                                     "committed": a.get(key), "fresh": b.get(key)})
        if _ids(old) != _ids(new):
            id_churn.append(name)
        if old == new:
            identical += 1
    return {
        "number_drift": number_drift,
        "id_churn": id_churn,
        "missing": missing,
        "identical_files": identical,
        "claim": ("numbers must not drift: they are what a reader quotes. Entry-id churn is "
                  "expected after any schema change and is reported as the evidence's AGE, "
                  "not as a failure - comparing bytes would fail on every harmless addition "
                  "and the check would be switched off"),
    }


if __name__ == "__main__":
    print(json.dumps(compare(), indent=2))
