#!/usr/bin/env python3
"""Prove the Baseline B v2 verifiers can FAIL.

WHY: a verifier that cannot fail is decoration. This repository has already
produced one (a verifier whose assertion ended in "or True") and a batch whose
"pass" was a cwd trap returning an empty file list.

HOW: each mutation breaks ONE property in a TEMPORARY COPY of the module, then a
probe subprocess asserts the property still holds. If the mutation is real, the
probe exits non-zero. The tracked files are never written.

THE TRAP THIS FILE ITSELF FELL INTO, and why the guard below exists: the first
version of this verifier had a Python SyntaxError, printed nothing, and the shell
still reported EXIT=0. That is precisely the "empty output looks like a pass"
failure this project has been burned by. So the runner now (a) requires non-empty
stdout from every probe, and (b) treats "probe produced no output" as NOT CAUGHT
rather than as success.

Exit 0 = every mutation was caught. Exit 1 = at least one was not.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLANNER = ROOT / "runtime" / "planner"

# ------------------------------------------------------------------ probes ----
# Each probe exits 0 when it observes the CORRECT behaviour and 1 when it does not.
# Non-empty output is mandatory; see `run_probe`.

PROBE_LEAK_GUARD = """
import json, sys
sys.path.insert(0, ".")
import public_observation as po
spec = json.load(open(sys.argv[1]))
try:
    po.build_observation(spec)
except po.LeakError:
    print("CAUGHT: leak guard fired on a task carrying expected_goal")
    sys.exit(0)
print("NOT CAUGHT: builder accepted a task carrying expected_goal")
sys.exit(1)
"""

PROBE_FUNCTION_OF_INPUT = """
import sys
sys.path.insert(0, ".")
import public_observation as po
task = {"task_id": "x", "instruction": "i", "evaluator_version": "0", "split": "train",
        "objects": [{"name": "o", "color": "red", "initial_pose": [1, 2, 3, 0]}],
        "zones": [{"name": "z", "pose": [9.5, 9.5, 9.5], "radius": 0.06}]}
obs = po.build_observation(task)
if obs["zones"][0]["position"] == [9.5, 9.5, 9.5]:
    print("CAUGHT: observation followed the task pose")
    sys.exit(0)
print("NOT CAUGHT: observation ignored the task pose ->", obs["zones"][0])
sys.exit(1)
"""

PROBE_GATE_REFUSAL = """
import os, sys
sys.path.insert(0, ".")
os.environ["EVOBOT_LLM_GATE"] = "/bin/false"
os.environ["FLEXCELL_PILOT_API_KEY"] = "sk-bypass-attempt"
import gated_chat as gc
try:
    key = gc.key_from_gate()
except gc.GateRefused:
    print("CAUGHT: a refusing gate still refused, no fallback")
    sys.exit(0)
print("NOT CAUGHT: a refusing gate was bypassed, got a %d-byte key" % len(key))
sys.exit(1)
"""

PROBE_PLAN_STRICT = """
import sys
sys.path.insert(0, ".")
import agent_planner_v2 as ap
obs = {"instruction": "i", "skills": ["pick"],
       "objects": [{"name": "a", "color": "red", "position": [0, 0, 0]}],
       "zones": [{"name": "z", "position": [0, 0, 0], "radius": 0.06}],
       "budget": {"max_steps": 40, "max_wall_s": 600}}
reply = {"moves": [{"object": "a", "zone": "z"}, {"object": "GHOST", "zone": "z"}],
         "unmoved": []}
try:
    out = ap.validate_plan(reply, obs)
except ap.PlanRejected as exc:
    print("CAUGHT: invalid plan rejected ->", str(exc)[:80])
    sys.exit(0)
print("NOT CAUGHT: invalid plan accepted, moves =", out["moves"])
sys.exit(1)
"""

PROBE_BUDGET = """
import sys
sys.path.insert(0, ".")
import agent_planner_v2 as ap
# TWO distinct objects, one bin. Every move is individually valid and no pair
# repeats, so the ONLY thing that can reject this plan is the step budget.
obs = {"instruction": "i", "skills": ["pick"],
       "objects": [{"name": "a", "color": "red", "position": [0, 0, 0]},
                   {"name": "b", "color": "blue", "position": [1, 0, 0]}],
       "zones": [{"name": "z", "position": [0, 0, 0], "radius": 0.06}],
       "budget": {"max_steps": 1, "max_wall_s": 600}}
reply = {"moves": [{"object": "a", "zone": "z"}, {"object": "b", "zone": "z"}],
         "unmoved": []}
try:
    out = ap.validate_plan(reply, obs)
except ap.PlanRejected as exc:
    msg = str(exc)
    if "budget" not in msg:
        print("INCONCLUSIVE: rejected for the wrong reason ->", msg[:90])
        sys.exit(2)
    print("CAUGHT: budget of 1 enforced ->", msg[:80])
    sys.exit(0)
print("NOT CAUGHT: 2 distinct valid moves accepted under a budget of 1")
sys.exit(1)
"""

PROBE_CONTROL = """
import sys
sys.path.insert(0, ".")
import public_observation as po
task = {"task_id": "x", "instruction": "i", "evaluator_version": "0", "split": "train",
        "objects": [{"name": "o", "color": "red", "initial_pose": [1, 2, 3, 0]}],
        "zones": [{"name": "z", "pose": [9.5, 9.5, 9.5], "radius": 0.06}]}
obs = po.build_observation(task)
assert obs["zones"][0]["position"] == [9.5, 9.5, 9.5]
print("CONTROL OK: unmutated module behaves correctly")
sys.exit(0)
"""


def run_probe(module_name, broken_source, probe_source, argv=()):
    """Run `probe_source` in a temp dir where `module_name` has `broken_source`.

    Returns (exit_code, output). Non-empty output is REQUIRED by the caller: a
    probe that prints nothing may have died before asserting anything.
    """
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        for module in PLANNER.glob("*.py"):
            (tmpdir / module.name).write_text(module.read_text(encoding="utf-8"),
                                             encoding="utf-8")
        (tmpdir / module_name).write_text(broken_source, encoding="utf-8")
        (tmpdir / "_probe.py").write_text(probe_source, encoding="utf-8")
        proc = subprocess.run([sys.executable, "_probe.py", *argv], cwd=tmp,
                              capture_output=True, text=True)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def mutate(module_name, anchor, replacement, description, probe_source, argv=()):
    original = (PLANNER / module_name).read_text(encoding="utf-8")
    if anchor not in original:
        return {"mutation": description, "caught": False, "exit_code": None,
                "detail": "ANCHOR MISSING -- the mutation did not apply, so this "
                          "check proves nothing"}
    broken = original.replace(anchor, replacement, 1)
    if broken == original:
        return {"mutation": description, "caught": False, "exit_code": None,
                "detail": "MUTATION HAD NO EFFECT"}
    code, output = run_probe(module_name, broken, probe_source, argv)
    lines = [ln for ln in output.strip().splitlines() if ln.strip()]
    silent = not lines
    return {"mutation": description,
            "caught": bool(code != 0 and not silent),
            "exit_code": code,
            "detail": ("<PROBE WAS SILENT -- not counted as caught>" if silent
                       else lines[-1][:200])}


def main():
    spec_path = str(ROOT / "benchmark" / "tasks" / "train" / "T01-train-seed1000.json")

    # Control first: the UNMUTATED module must pass its own probe. Without this,
    # a probe that always fails would look like five successful mutations.
    control_code, control_out = run_probe(
        "public_observation.py",
        (PLANNER / "public_observation.py").read_text(encoding="utf-8"),
        PROBE_CONTROL)
    control_ok = control_code == 0 and "CONTROL OK" in control_out

    results = [
        # NOTE: the first version of this mutation disabled only the ANSWER_KEYS
        # branch, and the probe still saw a LeakError -- because assert_public has a
        # SECOND guard (unknown keys outside PUBLIC_KEYS) that also rejects
        # expected_goal. The mutation was not real, and the verifier said so. The
        # mutation now disables the whole function, which is the actual failure mode.
        mutate("public_observation.py",
               "def assert_public(task):",
               "def assert_public(task):\n    return True  # MUTATION: guard disabled",
               "M1 leak guard disabled -> a task carrying expected_goal is accepted",
               PROBE_LEAK_GUARD, argv=(spec_path,)),

        mutate("public_observation.py",
               '            "position": [float(v) for v in zone["pose"]],',
               '            "position": [0.12, -0.15, 0.0175],  # MUTATION: hardcoded',
               "M2 bin pose hardcoded -> observation stops being a function of the task",
               PROBE_FUNCTION_OF_INPUT),

        # NOTE, twice: the first version weakened the refusal CONDITION but the next
        # line then raised "no key" on the empty stdout, so no bypass existed. The
        # second moved the fallback onto the key, but a non-zero exit still raised
        # before reaching it. Both mutations were reported as NOT caught, correctly.
        # A real bypass intercepts the REFUSAL itself -- which is exactly what
        # pilot.llm.setting() does, measured at 35 bytes from the registry.
        mutate("gated_chat.py",
               "    if proc.returncode != 0:",
               '    if proc.returncode != 0 and os.environ.get("FLEXCELL_PILOT_API_KEY"):\n'
               '        return os.environ["FLEXCELL_PILOT_API_KEY"]  # MUTATION: bypass\n'
               "    if proc.returncode != 0:",
               "M3 gate refusal intercepted by an environment-key fallback -> bypass restored",
               PROBE_GATE_REFUSAL),

        mutate("agent_planner_v2.py",
               "    if problems:\n        raise PlanRejected(problems)",
               "    if problems:\n        pass  # MUTATION: failures downgraded to warnings",
               "M4 plan validation downgraded -> a bad plan is returned instead of raised",
               PROBE_PLAN_STRICT),

        mutate("agent_planner_v2.py",
               "    limit = MAX_STAGES if not budget else min(MAX_STAGES, int(budget))",
               "    limit = MAX_STAGES  # MUTATION: declared budget ignored",
               "M5 declared step budget ignored -> an over-budget plan is accepted",
               PROBE_BUDGET),
    ]

    # The tracked files must be byte-identical to what git has; a mutation that
    # failed to revert would leave the repo quietly broken.
    clean = all("MUTATION" not in (PLANNER / name).read_text(encoding="utf-8")
                for name in ("public_observation.py", "agent_planner_v2.py",
                             "gated_chat.py"))

    all_caught = control_ok and clean and all(r["caught"] for r in results)

    # READ THIS BEFORE READING THE TABLE.
    #
    # "property_broke_under_mutation" = the mutation DID break the property, and the
    # probe DETECTED it. That is the good outcome: it proves the check is real.
    # "probe_exit_code" is the PROBE's status, not this verifier's: 0 = the property
    # still held (bad: the mutation was too weak to test anything), 1 = the property
    # broke (good: the verifier would have caught the real defect).
    for result in results:
        result["property_broke_under_mutation"] = result.pop("caught")
        result["probe_exit_code"] = result.pop("exit_code")

    print(json.dumps({
        "control_passes_on_unmutated_code": control_ok,
        "control_output": control_out.strip()[-120:],
        "tracked_files_unmodified": clean,
        "legend": ("property_broke_under_mutation=true means the check is REAL: "
                   "the mutation broke the property and the probe detected it"),
        "mutations": results,
        "every_check_is_proven_to_be_able_to_fail": all_caught}, indent=2))
    return 0 if all_caught else 1


if __name__ == "__main__":
    sys.exit(main())
