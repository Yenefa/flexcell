"""The pre-registered defect instances must be reproducible and must actually bite.

TASKS.md names DEF-F1-REG and DEF-F2-MAP and leaves their realization to #252.
A manifest with "TBD" in the injection column is not an instance: nothing can be
injected, so the pre-registered slots cannot be run against the defect the
protocol names.

The first version of the F1 injection failed that test and the test did not
notice, because it asserted the wrong property (that the key was gone rather than
that nothing was registered). Both properties are checked below now, including
the one that was wrong: deleting the key does not empty the registry, it restores
the node's declared default.
"""
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFECTS = HERE / "defects"
CONFIG_REL = "src/flexcell/flexcell_skills/config/week1.yaml"
OBSERVE_REL = "src/flexcell/flexcell_skills/flexcell_skills/observe_server.py"
FSM_REL = "src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py"


def sha_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(defect):
    return json.loads((DEFECTS / defect / "manifest.json").read_text(encoding="utf-8"))


def declared_default():
    """What observe_server uses when the configuration is silent.

    Read out of the source rather than hard-coded, so this test keeps meaning
    something if the default ever changes.
    """
    text = (ROOT / OBSERVE_REL).read_text(encoding="utf-8")
    match = re.search(r"declare_parameter\('tracked_objects',\s*(\[[^\]]*\])\)", text)
    assert match, "the tracked_objects default is no longer declared the way this test reads it"
    return ast.literal_eval(match.group(1))


def effective_registry(params):
    """The registry a node would have, given its parameter dict."""
    return params.get("tracked_objects", declared_default())


def params_of(path):
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["observe_server"]["ros__parameters"]


# ---------------------------------------------------------------- F1: config
def test_f1_override_digest_matches_the_manifest():
    info = manifest("DEF-F1-REG")
    assert sha_of(DEFECTS / "DEF-F1-REG" / info["artifact"]) == info["artifact_sha256"]


def test_f1_injection_leaves_no_real_object_registered():
    """The property that matters: nothing the perception layer can observe.

    Not "the list is empty". An empty list is not a valid rclpy parameter
    override - measured on 2026-11-16, both through a params file and through
    --ros-args -p, and both times the node died with
    ParameterUninitializedException. So the injection registers a name the world
    does not contain, which leaves the node running and no demo object observed.
    """
    override = DEFECTS / "DEF-F1-REG" / "override.yaml"
    tracked = effective_registry(params_of(override))
    real = effective_registry(params_of(ROOT / CONFIG_REL))
    assert tracked, "an empty list would crash the node instead of the task"
    assert not set(tracked) & set(real), tracked


def test_f1_deleting_the_key_would_have_restored_the_default():
    """The mistake this injection originally made, kept as a test.

    observe_server declares its default as the two demo objects, so a config that
    simply omits the key registers both of them. An injection built that way puts
    a healthy system in the 'broken' slot and no condition can tell the
    difference.
    """
    yaml = pytest.importorskip("yaml")
    pristine = params_of(ROOT / CONFIG_REL)
    without_key = {k: v for k, v in pristine.items() if k != "tracked_objects"}
    assert effective_registry(without_key) == declared_default() != []
    override = effective_registry(params_of(DEFECTS / "DEF-F1-REG" / "override.yaml"))
    assert override and not set(override) & set(declared_default())


def test_f1_override_changes_only_the_registry_line():
    override = (DEFECTS / "DEF-F1-REG" / "override.yaml").read_text(encoding="utf-8").splitlines()
    pristine = (ROOT / CONFIG_REL).read_text(encoding="utf-8").splitlines()
    assert len(override) == len(pristine)
    differing = [(a, b) for a, b in zip(pristine, override) if a != b]
    assert len(differing) == 1, differing
    assert "tracked_objects" in differing[0][0]


def test_f1_override_keeps_the_rest_of_the_config_loadable():
    params = params_of(DEFECTS / "DEF-F1-REG" / "override.yaml")
    assert params["zones"] == ["zone_1", "zone_2"]
    assert params["zone_zone_1_x"] == 0.12


def test_f1_pristine_config_still_registers_the_demo_objects():
    assert sha_of(ROOT / CONFIG_REL) == manifest("DEF-F1-REG")["pristine_sha256"]
    assert effective_registry(params_of(ROOT / CONFIG_REL)) == ["target_box_a", "target_box_b"]


# ---------------------------------------------------------------- F2: source
def test_f2_patch_digest_matches_the_manifest():
    info = manifest("DEF-F2-MAP")
    assert sha_of(DEFECTS / "DEF-F2-MAP" / info["artifact"]) == info["artifact_sha256"]


def test_f2_patch_applies_to_the_pristine_source(tmp_path):
    target = tmp_path / FSM_REL
    target.parent.mkdir(parents=True)
    shutil.copyfile(ROOT / FSM_REL, target)
    ran = subprocess.run(["patch", "-p1", "--batch", "-i",
                          str(DEFECTS / "DEF-F2-MAP" / "inject.patch")],
                         cwd=tmp_path, capture_output=True, text=True)
    assert ran.returncode == 0, ran.stdout + ran.stderr
    injured = target.read_text(encoding="utf-8")
    assert "((self._obj_a, 'zone_2'), (self._obj_b, 'zone_1'))" in injured
    assert "((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))" not in injured


def test_f2_patch_touches_only_the_stated_file():
    info = manifest("DEF-F2-MAP")
    patch = (DEFECTS / "DEF-F2-MAP" / "inject.patch").read_text(encoding="utf-8")
    headers = [l for l in patch.splitlines() if l.startswith("+++ ")]
    assert len(headers) == 1
    assert headers[0].endswith(info["affected_files"][0])


def test_f2_pristine_source_still_carries_the_healthy_mapping():
    assert sha_of(ROOT / FSM_REL) == manifest("DEF-F2-MAP")["pristine_sha256"]
    assert "((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))" in \
        (ROOT / FSM_REL).read_text(encoding="utf-8")


# ------------------------------------------------- F2: does it change behaviour?
def _declared(name):
    """The default value a parameter is declared with, read from the node source."""
    text = (ROOT / FSM_REL).read_text(encoding="utf-8")
    match = re.search(r"declare_parameter\('%s',\s*'([^']*)'\)" % name, text)
    assert match, "parameter %r is no longer declared the way this test reads it" % name
    return match.group(1)


def _assignments_in(source_text, a, b):
    """Pull the demo assignment tuple out of the node source and resolve it.

    The tuple is written as ((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2')),
    so it cannot be literal_eval'd directly. Substituting the two declared
    defaults is what the running node does with them, and taking those defaults
    from the source means this test follows the code instead of hard-coding it.
    """
    # the demo branch of the single-or-demo conditional; the single branch names
    # one object taken from the request and is not what this defect is about
    match = re.search(
        r"\(\((self\._obj_a, 'zone_\d')\), \((self\._obj_b, 'zone_\d')\)\)",
        source_text)
    assert match, "the demo assignment is no longer written the way this test reads it"
    expression = match.group(0)
    expression = expression.replace("self._obj_a", repr(a)).replace("self._obj_b", repr(b))
    return ast.literal_eval(expression)


def _policy():
    """Import the repository's own decision policy, not the installed overlay."""
    for path in (str(ROOT / "src" / "flexcell" / "flexcell_skills"),
                 str(ROOT / "src" / "flexcell")):
        if path not in sys.path:
            sys.path.insert(0, path)
    from flexcell_skills import decision_policy as dp
    return dp


def _constraints(dp):
    return dp.Constraints(
        allowed_actions=frozenset(("OBSERVE", "PICK", "PLACE", "VERIFY", "WAIT", "ABORT")),
        recovery_budget=1, verify_tolerance_m=0.06,
        motion_profile_id="demo_slow", max_world_age_s=1.5)


def _h(dp, action, target):
    return dp.HistoryRecord(action=action, target=target, outcome=0, error_code=0,
                            attempt=1, world_revision=3, evidence_id="e")


def _place_target(dp, assignments):
    """Drive the FSM to the first PLACE and report its target (the object id)."""
    goal = dp.TaskGoal(goal_id="g", scenario_id="s", assignments=assignments)
    first = assignments[0][0]
    history = (_h(dp, "OBSERVE", first), _h(dp, "PICK", first))
    decision = dp.FSMPolicy().decide(None, goal, _constraints(dp), history)
    assert decision.action == "PLACE", decision
    return decision.target


def test_f2_patch_swaps_where_each_object_is_sent_without_moving_the_plan():
    """What the patch actually changes, checked against the real decision layer.

    I first wrote this as "the policy's PLACE decision names the other zone" and
    it failed, correctly: Decision.target is the object id and nothing else. The
    zone lives in TaskGoal.assignments and reaches the executor through it, so
    the checkable claim is the one made here - the plan order is unchanged, the
    zone each object is sent to is swapped, and the decision layer still walks
    the same objects.

    Round 20 found the F1 injection had never been run. This is the same check
    for F2: the artifact's effect, observed in the module that would act on it.
    """
    dp = _policy()
    a, b = _declared("object_a"), _declared("object_b")
    healthy_text = (ROOT / FSM_REL).read_text(encoding="utf-8")
    injured_text = healthy_text.replace(
        "((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))",
        "((self._obj_a, 'zone_2'), (self._obj_b, 'zone_1'))")
    assert injured_text != healthy_text

    healthy = _assignments_in(healthy_text, a, b)
    injured = _assignments_in(injured_text, a, b)
    assert [o for o, _ in healthy] == [o for o, _ in injured] == [a, b]
    assert dict(healthy)[a] == "zone_1" and dict(injured)[a] == "zone_2"

    # the decision layer walks the same objects in the same order under both
    for assignments in (healthy, injured):
        goal = dp.TaskGoal(goal_id="g", scenario_id="s", assignments=assignments)
        decision = dp.FSMPolicy().decide(None, goal, _constraints(dp),
                                         (_h(dp, "OBSERVE", a), _h(dp, "PICK", a)))
        assert decision.action == "PLACE" and decision.target == a


def test_f2_swapping_the_mapping_moves_both_objects():
    dp = _policy()
    a, b = _declared("object_a"), _declared("object_b")
    healthy = _assignments_in((ROOT / FSM_REL).read_text(encoding="utf-8"), a, b)
    injured = _assignments_in(
        (ROOT / FSM_REL).read_text(encoding="utf-8").replace(
            "((self._obj_a, 'zone_1'), (self._obj_b, 'zone_2'))",
            "((self._obj_a, 'zone_2'), (self._obj_b, 'zone_1'))"), a, b)
    assert dict(healthy) == {a: "zone_1", b: "zone_2"}
    assert dict(injured) == {a: "zone_2", b: "zone_1"}
