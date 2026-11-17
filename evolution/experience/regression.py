#!/usr/bin/env python3
"""Regression gate for EXPERIENCE activation: no new failures, or the version is not kept.

WHY THIS IS SEPARATE FROM evolution/validation/gate_differential.py
    That gate judges a PROPOSAL that changes source. This one judges an experience ENTRY
    that is about to become ACTIVE, and it answers a different question: if this entry
    starts steering behaviour, does the existing evidence still hold? The two gates share
    the differential idea (new failures reject, baselined failures do not) and the pinned
    verifier list, but they must not share an implementation: an entry that changes no
    file would pass a source-diff gate trivially, which is exactly the vacuous pass that
    gate_differential.py was written to avoid.

THE THREE OUTCOMES
    KEEP     no new failures among the verifiers that ran
    REVERT   a NEW failure appeared; the version must not be activated
    UNKNOWN  the gate could not run (no verifiers, unreadable baseline). Not a pass.

    UNKNOWN is deliberately distinct from KEEP. Every earlier gate in this repository
    that treated "could not check" as "fine" ended up admitting a bad record.

SCOPE
    The verifier subset is chosen by the entry's consumer, because a spacing entry and a
    recovery entry exercise different code. Running all 109 verifiers would take minutes
    and would mostly test unrelated batches; the subset is pinned here so it is visible
    and reviewable, and the baseline file is the same one the source gate uses.
"""
import glob
import json
import os
import subprocess
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
ACCEPTANCE = WT / "setup" / "acceptance"
KNOWN = WT / "evolution" / "validation" / "known_failures.json"

# Pinned per consumer. Each batch here exercises the consumer's code path.
# A per-consumer pin is a HINT, not the gate's scope.
#
# WHY THE PIN WAS NOT ENOUGH: it named two verifiers out of seventy. So "old-task
# regression" covered 2 of the repository's 70 offline acceptance checks, and an entry that
# broke any of the other 68 would have passed the gate. Reporting "regression KEEP" on that
# basis is a claim the check could not support.
#
# The scope is now every verifier in the checkout (see all_verifiers). The pin survives
# only as a fast subset for a caller that asks for one. Of the 70, 18 fail on the PR base
# commit 39016694 as well - measured, not assumed - and those are baselined in
# evolution/validation/known_failures.json with the reason each cannot be attributed to any
# entry. A gate requires NO NEW failures; it does not require a green repository, because
# a gate that requires the impossible gets switched off, which is what had already happened.
CONSUMER_VERIFIERS = {
    "spread_policy": ["evobot_spacing_fix_20261111", "evobot_lesson_routing_20261111"],
    "executor_recovery": ["evobot_spacing_fix_20261111", "evobot_lesson_routing_20261111"],
    "planner": ["evobot_lesson_routing_20261111"],
    "harness": ["evobot_lesson_routing_20261111"],
    "development": ["evobot_lesson_routing_20261111"],
}

ACCEPTANCE = os.path.join(WT, "setup", "acceptance")


class GateError(ValueError):
    """The gate was asked something it cannot answer. Never silently becomes a pass."""


def all_verifiers(acceptance=None, exclude_self=True):
    """Every acceptance verifier in the checkout, sorted. This is the gate's scope.

    WHY NOT A PINNED SUBSET: the pin named 2 of 70. An entry that broke any of the other 68
    would have been reported as "regression KEEP". Scoping the gate by hand is how a check
    comes to cover the part of the system somebody already thought about.

    SELF-EXCLUSION IS NOT A CONVENIENCE. The chain verifier runs the demo, the demo's
    activation calls this gate, and the gate ran every verifier - including the chain
    verifier. So the gate ended up re-running itself, and the only thing it reported as a
    NEW failure was the verifier that contains it: a REVERT caused by recursion, not by a
    regression. Excluding the caller breaks the cycle, and the exclusion is NAMED in
    gate_activation so the coverage gap is visible rather than silent.
    """
    root = acceptance or ACCEPTANCE
    names = sorted(os.path.basename(os.path.dirname(p))
                   for p in glob.glob(os.path.join(root, "evobot_*", "verify.py")))
    if exclude_self:
        names = [n for n in names if n not in SELF_VERIFIERS]
    return names


# Verifiers that contain this gate, and therefore cannot be run BY it. Listed explicitly:
# an exclusion by glob would silently grow to cover whatever somebody wanted to skip.
SELF_VERIFIERS = ("evobot_continual_chain_20261118",)


def load_known(path=KNOWN):
    """Verifiers that fail INDEPENDENTLY of any entry. Absent file -> None, not {}."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {f["verifier"] for f in doc.get("failures") or []}


def run_verifier(name, acceptance=None):
    """Run one batch verifier. Returns (ok, detail). A timeout is a FAILURE, not a pass."""
    root = Path(acceptance or ACCEPTANCE)
    script = root / name / "verify.py"
    if not script.exists():
        return False, "verifier missing: %s" % script
    try:
        proc = subprocess.run([sys.executable, str(script)], capture_output=True,
                              text=True, timeout=300, cwd=str(script.parent))
    except subprocess.TimeoutExpired:
        return False, "verifier timed out after 300 s"
    if proc.returncode != 0:
        tail = ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()
        return False, tail[-1][:160] if tail else "exit %d" % proc.returncode
    return True, "ok"


def check(entry, acceptance=None, known_path=None, runner=run_verifier):
    """Gate one entry. Returns a verdict dict; never raises for a verifier failure."""
    consumer = entry.get("consumer")
    # Scope = every verifier, not the consumer's pin. A pin that named 2 of 70 made
    # "nothing that used to work stopped working" a claim about 2 checks.
    names = all_verifiers(acceptance)
    if not names:
        return {"verdict": "UNKNOWN",
                "why": "no verifier found under %r; refusing to report KEEP with nothing "
                       "to check" % (acceptance or ACCEPTANCE,),
                "ran": [], "new_failures": [], "baselined": []}
    known = load_known(known_path or KNOWN)
    if known is None:
        # FAIL CLOSED. A missing baseline must not become a free pass, which is the
        # exact bug gate_differential.py documents having had.
        return {"verdict": "UNKNOWN",
                "why": "known_failures.json missing or unreadable; refusing to guess",
                "ran": [], "new_failures": [], "baselined": []}
    ran, failing, details = [], [], {}
    for name in names:
        ok, detail = runner(name, acceptance)
        ran.append(name)
        if not ok:
            failing.append(name)
            details[name] = detail
    new = sorted(set(failing) - known)
    baselined = sorted(set(failing) & known)
    # A baselined verifier that now PASSES is good news, not a failure - but the baseline
    # must be corrected or it silently grows into a permanent excuse. Reported so a stale
    # entry is visible rather than inherited forever.
    recovered = sorted(set(known) & set(ran) - set(failing))
    verdict = "REVERT" if new else "KEEP"
    return {"verdict": verdict, "ran": ran, "new_failures": new,
            "baselined": baselined, "details": details,
            "excluded_self": [n for n in SELF_VERIFIERS],
            "recovered": recovered,
            "why": ("%d verifier(s) ran; %d new failure(s); %d baselined; %d excluded as "
                    "self-referential; %d baselined entry(ies) now pass and should be "
                    "removed from the baseline"
                    % (len(ran), len(new), len(baselined), len(SELF_VERIFIERS),
                       len(recovered)))}


def gate_activation(entry, validation, acceptance=None, known_path=None, runner=run_verifier):
    """Decide whether a reviewed entry may be activated.

    A REJECT review is honoured as-is (it never activates). An ACCEPT review is only
    enough when the regression gate says KEEP; KEEP is what turns "a reviewer approved
    this" into "and nothing that used to work stopped working".
    """
    if (validation or {}).get("review_verdict") != "ACCEPT":
        return {"activate": False, "why": "review verdict is not ACCEPT"}
    result = check(entry, acceptance=acceptance, known_path=known_path, runner=runner)
    if result["verdict"] != "KEEP":
        return {"activate": False, "regression": result,
                "why": "regression gate said %s" % result["verdict"]}
    return {"activate": True, "regression": result,
            "why": "review ACCEPT and regression KEEP"}


if __name__ == "__main__":
    doc = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    print(json.dumps(check(doc), indent=2))
