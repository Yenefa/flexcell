"""The pre-registered defect instances, as runnable candidate workspaces.

WHY THIS EXISTS
    dry_run_matrix.py builds synthetic fixtures (skill/registry.py and friends).
    They exercise the machinery, and nothing else: the twenty-four slots in
    RUN_MANIFEST name DEF-F1-REG and DEF-F2-MAP, which are the workcell's
    perception configuration and its object-to-zone mapping. Running the manifest
    slots against the synthetic fixtures would be substituting a different
    experiment for the pre-registered one.

    This module turns the two artifacts under defects/ into workspaces a repairer
    can actually be pointed at:

        <root>/config/week1.yaml            (F1: the editable surface)
        <root>/src/task_fsm_server.py       (F2: the editable surface)
        <root>/task.md                      (what the repairer is told)
        <root>/gate/check.py                (the sealed check; never edited)

    The gate is a separate script rather than an import, so the candidate cannot
    reach it and the repairer cannot read its thresholds by importing something.

WHAT IT DOES NOT DO
    It does not judge whether a repair is good enough for the paper. It answers
    one question per instance - is the observable the protocol names present? -
    and the answer is a typed code, not a verdict.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFECTS = HERE / "defects"

CONFIG_REL = "src/flexcell/flexcell_skills/config/week1.yaml"
OBSERVE_REL = "src/flexcell/flexcell_skills/flexcell_skills/observe_server.py"
FSM_REL = "src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py"

FAMILIES = ("DEF-F1-REG", "DEF-F2-MAP")

EXPECTED_ASSIGNMENTS = {("target_box_a", "zone_1"), ("target_box_b", "zone_2")}

GATE = r'''
import json, re, sys
from pathlib import Path

root = Path(sys.argv[1])
family = sys.argv[2]

def declared_default():
    text = (root / "gate" / "observe_server.py").read_text(encoding="utf-8")
    m = re.search(r"declare_parameter\('tracked_objects',\s*(\[[^\]]*\])\)", text)
    return eval(m.group(1))

if family == "DEF-F1-REG":
    import yaml
    params = yaml.safe_load((root / "config" / "week1.yaml").read_text(encoding="utf-8"))
    params = params["observe_server"]["ros__parameters"]
    tracked = params.get("tracked_objects", declared_default())
    real = {"target_box_a", "target_box_b"}
    # The gate passes when the repair is correct, not when the defect is present.
    # The first version of this line read "no real object is registered", which
    # is true of the injected workspace - so every unrepaired F1 slot would have
    # been graded as a pass. The dry run caught it because it hands the gate both
    # a broken and a repaired workspace and requires the answers to differ.
    ok = real.issubset(set(tracked))
    print(json.dumps({"ok": ok,
                      "code": "PASS" if ok else "OBJECT_NOT_REGISTERED",
                      "tracked": list(tracked)}))
else:
    text = (root / "src" / "task_fsm_server.py").read_text(encoding="utf-8")
    a = re.search(r"declare_parameter\('object_a',\s*'([^']*)'\)", text).group(1)
    b = re.search(r"declare_parameter\('object_b',\s*'([^']*)'\)", text).group(1)
    m = re.search(r"\(\((self\._obj_a, 'zone_\d')\), \((self\._obj_b, 'zone_\d')\)\)", text)
    if not m:
        print(json.dumps({"ok": False, "code": "ASSIGNMENT_UNPARSEABLE"}))
        sys.exit(0)
    expr = m.group(0).replace("self._obj_a", repr(a)).replace("self._obj_b", repr(b))
    got = set(eval(expr))
    expected = {("target_box_a", "zone_1"), ("target_box_b", "zone_2")}
    ok = got == expected
    print(json.dumps({"ok": ok,
                      "code": "PASS" if ok else "WRONG_ZONE_ASSIGNMENT",
                      "assignments": sorted(got)}))
'''

TASK_TEXT = {
    "DEF-F1-REG": (
        "The robot cannot see the objects it is asked to move. The perception "
        "service starts, but it never reports target_box_a or target_box_b, so "
        "every task fails before the first pick.\n\n"
        "The repair surface is the workcell configuration: config/week1.yaml. "
        "The gate checks that the perception service ends up tracking the demo "
        "objects; it does not tell you how."),
    "DEF-F2-MAP": (
        "The robot picks target_box_a but places it in the wrong zone. The demo "
        "assignment in the task FSM pairs each object with the other object's "
        "zone.\n\n"
        "The repair surface is source: src/task_fsm_server.py. The gate checks "
        "the demo assignment pairs target_box_a with zone_1 and target_box_b "
        "with zone_2."),
}


def artifact(family):
    return json.loads((DEFECTS / family / "manifest.json").read_text(encoding="utf-8"))


def editable_rel(family):
    return "config/week1.yaml" if family == "DEF-F1-REG" else "src/task_fsm_server.py"


def injected_text(family):
    """The broken content, as the artifact defines it."""
    info = artifact(family)
    if family == "DEF-F1-REG":
        return (DEFECTS / family / info["artifact"]).read_text(encoding="utf-8")
    source = (ROOT / FSM_REL).read_text(encoding="utf-8")
    patch = (DEFECTS / family / info["artifact"]).read_text(encoding="utf-8")
    added = [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]
    removed = [l[1:] for l in patch.splitlines() if l.startswith("-") and not l.startswith("---")]
    assert len(removed) == 1 and len(added) == 1, "expected a one-line patch"
    assert source.count(removed[0]) == 1, "the pristine source does not contain the removed line once"
    return source.replace(removed[0], added[0])


def healthy_text(family):
    """What a correct repair looks like. Used only to prove the gate can pass."""
    if family == "DEF-F1-REG":
        return (ROOT / CONFIG_REL).read_text(encoding="utf-8")
    return (ROOT / FSM_REL).read_text(encoding="utf-8")


def editable_path(family, root):
    """Where the repairer is allowed to write, for this instance."""
    return Path(root) / editable_rel(family)


def materialize(family, root):
    """Write an injected candidate workspace. Returns the workspace root.

    It used to return the editable file path, and the caller that wanted a
    directory spent one round passing a YAML file where a workspace belonged.
    Returning the root and offering editable_path() for the other need removes
    the ambiguity instead of leaving a note about it.
    """
    root = Path(root)
    rel = editable_rel(family)
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(injected_text(family), encoding="utf-8")
    (root / "task.md").write_text(TASK_TEXT[family], encoding="utf-8")
    gate = root / "gate"
    gate.mkdir(exist_ok=True)
    (gate / "check.py").write_text(GATE, encoding="utf-8")
    (gate / "observe_server.py").write_text((ROOT / OBSERVE_REL).read_text(encoding="utf-8"),
                                            encoding="utf-8")
    return root


def check(family, root):
    """Run the sealed gate. Returns (ok, payload)."""
    root = Path(root)
    ran = subprocess.run([sys.executable, str(root / "gate" / "check.py"), str(root), family],
                         capture_output=True, text=True)
    if ran.returncode != 0:
        return False, {"code": "GATE_FAILED", "detail": (ran.stderr or ran.stdout)[-300:]}
    payload = json.loads(ran.stdout.strip().splitlines()[-1])
    return bool(payload.get("ok")), payload


def apply_reference_fix(family, root):
    """Write the healthy content. Exists so the gate can be shown to pass."""
    target = Path(root) / editable_rel(family)
    target.write_text(healthy_text(family), encoding="utf-8")
    return target
