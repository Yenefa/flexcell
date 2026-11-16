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

from task_variants import VARIANTS, TASK_TEXT_V2
import layouts
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
variant = sys.argv[3] if len(sys.argv) > 3 else "v1"


def emit(ok, code, **extra):
    payload = {"ok": ok, "code": code}
    payload.update(extra)
    print(json.dumps(payload))
    sys.exit(0)


if family == "DEF-F1-REG":
    import yaml
    raw = (root / "config" / "week1.yaml").read_text(encoding="utf-8")
    try:
        parsed = yaml.safe_load(raw)
    except Exception as exc:
        # The candidate's own output is unreadable. That is a property of the
        # repair, not of the harness, and it must not be reported as a harness
        # fault: an earlier version raised here and every slot came back
        # GATE_FAILED, which reads the same whether the repair or the gate broke.
        emit(False, "CONFIG_UNPARSEABLE", detail=str(exc).splitlines()[0][:120])
    if not isinstance(parsed, dict) or "observe_server" not in parsed:
        emit(False, "CONFIG_SECTION_MISSING", detail="no observe_server section")
    node = parsed["observe_server"]
    if not isinstance(node, dict) or "ros__parameters" not in node:
        emit(False, "CONFIG_PARAMS_MISSING", detail="no ros__parameters under observe_server")
    params = node["ros__parameters"]
    if not isinstance(params, dict):
        emit(False, "CONFIG_PARAMS_MALFORMED", detail="ros__parameters is not a mapping")
    # An absent key is not a repair. ROS would fall back to the node's
    # declared default - which happens to be the healthy list - so deleting the
    # line used to pass the gate without knowing anything. Measured on
    # 2026-11-17: delete the line -> PASS with the default; empty list ->
    # OBJECT_NOT_REGISTERED. The acceptance rule is that the configuration states
    # the objects, so absence is its own failure code.
    if "tracked_objects" not in params:
        emit(False, "TRACKED_OBJECTS_ABSENT",
             detail="the configuration does not set tracked_objects")
    tracked = params["tracked_objects"]
    if not isinstance(tracked, list):
        emit(False, "CONFIG_BAD_TYPE", detail="tracked_objects is %s" % type(tracked).__name__)
    real = {"target_box_a", "target_box_b"}
    ok = real.issubset(set(tracked))
    # A layout is held out when its geometry must survive the repair. A repair
    # that rewrites the file and hardcodes one layout's coordinates is exactly
    # what the hold-out is for, so the gate compares what the configuration says
    # against the layout the workspace was built with.
    layout_file = root / "layout.json"
    if ok and layout_file.exists():
        want = json.loads(layout_file.read_text(encoding="utf-8"))["zones"]
        got = {}
        for key, field in (("zone_zone_1_x", "zone_1_x"), ("zone_zone_1_y", "zone_1_y"),
                          ("zone_zone_1_z", "zone_1_z"), ("zone_zone_2_x", "zone_2_x"),
                          ("zone_zone_2_y", "zone_2_y"), ("zone_zone_2_z", "zone_2_z")):
            if key in params:
                got[field] = params[key]
        for field, value in want.items():
            if field in got and abs(float(got[field]) - float(value)) > 1e-9:
                emit(False, "LAYOUT_VALUES_CHANGED",
                     detail="%s is %s, the layout says %s" % (field, got[field], value))
    # v2 withholds the names from the task text, so the failure has to
    # report what the workcell expected. That is execution feedback: B, C
    # and D may read it, A may not, and the boundary is what enforces that.
    extra = {}
    if variant == "v2" and not ok:
        extra["expected_objects"] = sorted(real)
    ok = real.issubset(set(tracked))
    emit(ok, "PASS" if ok else "OBJECT_NOT_REGISTERED", tracked=[str(t) for t in tracked], **extra)

text = (root / "src" / "task_fsm_server.py").read_text(encoding="utf-8")
try:
    a = re.search(r"declare_parameter\('object_a',\s*'([^']*)'\)", text).group(1)
    b = re.search(r"declare_parameter\('object_b',\s*'([^']*)'\)", text).group(1)
except AttributeError:
    emit(False, "SOURCE_UNPARSEABLE", detail="object_a/object_b declaration missing")
m = re.search(r"\(\((self\._obj_a, 'zone_\d')\), \((self\._obj_b, 'zone_\d')\)\)", text)
if not m:
    emit(False, "ASSIGNMENT_UNPARSEABLE", detail="the demo assignment is gone")
expr = m.group(0).replace("self._obj_a", repr(a)).replace("self._obj_b", repr(b))
got = set(eval(expr))
expected = {("target_box_a", "zone_1"), ("target_box_b", "zone_2")}
ok = got == expected
emit(ok, "PASS" if ok else "WRONG_ZONE_ASSIGNMENT", assignments=sorted(got))
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


def task_text(family, variant="v1"):
    if variant not in VARIANTS:
        raise ValueError("unknown task variant %r" % (variant,))
    return TASK_TEXT[family] if variant == "v1" else TASK_TEXT_V2[family]


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


def materialize(family, root, variant="v1", layout=None):
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
    (root / "task.md").write_text(task_text(family, variant), encoding="utf-8")
    if layout is not None:
        # The layout is the workcell geometry. It is written as data next to the
        # workspace so the gate can check the configuration still carries it.
        cfg = root / "config" / "week1.yaml"
        if cfg.exists():
            cfg.write_text(layouts.apply_to_config(cfg.read_text(encoding="utf-8"),
                                               layout), encoding="utf-8")
        (root / "layout.json").write_text(
            __import__("json").dumps({"layout": layout,
                                        "zones": layouts.layout_values(layout)}),
            encoding="utf-8")
    gate = root / "gate"
    gate.mkdir(exist_ok=True)
    (gate / "check.py").write_text(GATE, encoding="utf-8")
    (gate / "observe_server.py").write_text((ROOT / OBSERVE_REL).read_text(encoding="utf-8"),
                                            encoding="utf-8")
    return root


def check(family, root, variant="v1"):
    """Run the sealed gate. Returns (ok, payload)."""
    root = Path(root)
    ran = subprocess.run([sys.executable, str(root / "gate" / "check.py"), str(root), family, variant],
                         capture_output=True, text=True)
    if ran.returncode != 0:
        return False, {"code": "GATE_FAILED", "detail": (ran.stderr or ran.stdout)[-300:]}
    payload = json.loads(ran.stdout.strip().splitlines()[-1])
    return bool(payload.get("ok")), payload


def apply_reference_fix(family, root):
    """Apply the repair the way a careful repairer would: change what is wrong."""
    target = Path(root) / editable_rel(family)
    if family == "DEF-F1-REG":
        # Replacing only the offending line keeps everything else the workspace
        # was built with, including a held-out layout's coordinates. Writing the
        # whole healthy file instead passes on the layout it was written for and
        # silently reverts any other - which the hold-out is meant to catch.
        import re
        text = target.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^(\s*tracked_objects:\s*).*$",
                      lambda m: m.group(1) + "['target_box_a', 'target_box_b']", text)
        target.write_text(text, encoding="utf-8")
        return target
    target.write_text(healthy_text(family), encoding="utf-8")
    return target
