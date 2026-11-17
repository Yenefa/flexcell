
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
