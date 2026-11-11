#!/usr/bin/env python3
"""Baseline B v2 tests: the no-leak property, the gate, and the plan contract.

No network. The model is stubbed, so these test MY code, not how some model
happens to answer today. That distinction matters: a test that passes because
the model gave a good answer would break the moment the model changed, and would
have told me nothing about whether the code is correct.

Every test here is written to be able to FAIL. The two that carry the most weight
(no-leak and gate) are also proven by mutation in verify_baseline_b.py, because a
passing assertion is only evidence if the thing it asserts can be broken.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "planner"))

import agent_planner_v2 as ap
import gated_chat as gc
import public_observation as po

TRAIN = ROOT / "benchmark" / "tasks" / "train"


def _public(template="T01", seed=1000):
    spec = json.loads((TRAIN / ("%s-train-seed%d.json" % (template, seed))
                       ).read_text(encoding="utf-8"))
    return po.reduce_to_public(spec)


def _obs(template="T01", seed=1000):
    return po.build_observation(_public(template, seed))


class StubChat:
    """Returns a fixed reply and records the messages it was given."""

    def __init__(self, reply):
        self.reply = reply if isinstance(reply, str) else json.dumps(reply)
        self.seen = []

    def chat(self, messages):
        self.seen.append(messages)
        return {"content": self.reply, "tokens": 0, "seconds": 0.0, "model": "stub"}

    def metadata(self):
        return {"model": "stub"}


# ---------------------------------------------------------------- no-leak ----

def test_observation_is_refused_when_the_task_carries_the_answer():
    """The builder does not "avoid reading" expected_goal; it cannot be handed it."""
    spec = json.loads((TRAIN / "T01-train-seed1000.json").read_text(encoding="utf-8"))
    assert "expected_goal" in spec, "fixture assumption broken"
    with pytest.raises(po.LeakError) as err:
        po.build_observation(spec)
    assert "expected_goal" in str(err.value)


@pytest.mark.parametrize("key", sorted(po.ANSWER_KEYS))
def test_every_answer_key_is_rejected(key):
    task = _public()
    task[key] = {"anything": True}
    with pytest.raises(po.LeakError):
        po.build_observation(task)


def test_an_unknown_key_is_rejected_rather_than_ignored():
    task = _public()
    task["hint"] = "put box_a in zone_1"
    with pytest.raises(po.LeakError) as err:
        po.build_observation(task)
    assert "hint" in str(err.value)


def test_observation_is_a_function_of_the_task_it_was_given():
    """v1 FAILS this: it emitted colours and bin poses from module constants.

    Measured on v1: mutating the task's own color and zones[0].pose left the
    observation byte-identical. That is how a hardcoded world hides.
    """
    base = _public()
    before = po.build_observation(base)

    changed = json.loads(json.dumps(base))
    changed["objects"][0]["color"] = "GREEN_NOT_RED"
    changed["zones"][0]["pose"] = [9.5, 9.5, 9.5]
    after = po.build_observation(changed)

    assert after["objects"][0]["color"] == "GREEN_NOT_RED"
    assert after["zones"][0]["position"] == [9.5, 9.5, 9.5]
    assert before != after


def test_observation_offers_exactly_the_bins_the_task_declares():
    """v1 FAILS this on T02/T03: spec declares zone_1, v1 emitted zone_1+zone_2.

    A bin the task never offered is not an affordance; using it produces a plan
    that cannot be graded, which looks like a robot failure.
    """
    for template in ("T01", "T02", "T03", "T04", "T05", "T06"):
        public = _public(template)
        obs = po.build_observation(public)
        assert [z["name"] for z in obs["zones"]] == [z["name"] for z in public["zones"]], \
            template


def test_prompt_carries_no_answer_and_no_object_to_bin_pairing():
    """The v1 prompt was checked the same way. That check is what keeps it honest."""
    obs = _obs("T01")
    system, user = ap.build_prompt(obs)
    lowered = user.lower()
    for leak in ["expected", "placement", "evaluator", "tolerance", "unmoved",
                 "template", "seed"]:
        assert leak not in lowered, leak
    # no line may pair a specific object with a specific bin
    for line in user.splitlines():
        assert not ("target_box_" in line and "zone_" in line), line
    assert "target_box_a" in user and "zone_1" in user


def test_prompt_states_the_frame_convention_and_the_budget():
    system, user = ap.build_prompt(_obs("T01"))
    assert "+y is the robot LEFT" in user
    assert "Step budget" in user


# The observation names skills the way a human operator would; the wire protocol
# names actions the way ROS does. The two are NOT the same string, and pretending
# otherwise is how a made-up capability gets into a prompt. This table is the
# bridge, and it is checked in BOTH directions: every advertised skill must map to
# a real .action file, and every real action must be either advertised or
# explicitly listed as not-for-planning.
SKILL_TO_ACTION = {
    "observe": "Observe",
    "pick": "PickObject",
    "place": "PlaceObject",
    "verify": "VerifyObject",
    "move_to_pose": "MoveToPose",
    "run_composite": "RunComposite",
}

# Actions that exist on the robot but are deliberately NOT offered to the planner.
# RunDemo and RunPickPlace are fixed demo flows, not composable primitives; offering
# them would let the agent "plan" by invoking a canned task, which measures nothing.
ACTIONS_NOT_OFFERED = {"RunDemo", "RunPickPlace"}


def test_skills_named_in_the_observation_are_backed_by_real_actions():
    """A skill name no action backs would be an invented capability."""
    action_dir = ROOT / "src" / "flexcell" / "flexcell_interfaces" / "action"
    actions = {p.stem for p in action_dir.glob("*.action")}
    assert actions, "action definitions not found; the check would be vacuous"

    for skill in po.SKILLS:
        assert skill in SKILL_TO_ACTION, "%r has no action mapping" % skill
        assert SKILL_TO_ACTION[skill] in actions, \
            "%r maps to %r, which is not a real action" % (skill, SKILL_TO_ACTION[skill])

    covered = set(SKILL_TO_ACTION.values()) | ACTIONS_NOT_OFFERED
    assert covered == actions, (
        "advertised skills and real actions disagree: missing from the table %s, "
        "stale entries %s" % (sorted(actions - covered), sorted(covered - actions)))


# ------------------------------------------------------------------ gate ----

def test_a_missing_gate_is_fatal_not_a_silent_fallback(monkeypatch, tmp_path):
    """The whole point: no gate means no key, never "look elsewhere"."""
    monkeypatch.setenv(gc.GATE_ENV_OVERRIDE, str(tmp_path / "absent.sh"))
    with pytest.raises(gc.GateRefused) as err:
        gc.key_from_gate()
    assert "not found" in str(err.value)


def test_a_refusing_gate_is_fatal(monkeypatch, tmp_path):
    """Exit 3 is the gate saying "over budget" or "balance too low"."""
    gate = tmp_path / "gate.sh"
    gate.write_text("#!/bin/bash\necho 'EVOBOT_LLM_GATE: refused' >&2\nexit 3\n",
                    encoding="utf-8")
    monkeypatch.setenv(gc.GATE_ENV_OVERRIDE, str(gate))
    with pytest.raises(gc.GateRefused) as err:
        gc.key_from_gate()
    assert "exit 3" in str(err.value)


def test_a_gate_that_exits_zero_without_a_key_is_fatal(monkeypatch, tmp_path):
    gate = tmp_path / "gate.sh"
    gate.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    monkeypatch.setenv(gc.GATE_ENV_OVERRIDE, str(gate))
    with pytest.raises(gc.GateRefused) as err:
        gc.key_from_gate()
    assert "no key" in str(err.value)


def test_the_client_never_records_the_key_only_its_fingerprint(monkeypatch, tmp_path):
    gate = tmp_path / "gate.sh"
    gate.write_text("#!/bin/bash\nprintf 'sk-secret-value-abcdefghijklmnop'\n",
                    encoding="utf-8")
    monkeypatch.setenv(gc.GATE_ENV_OVERRIDE, str(gate))
    chat = gc.GatedChat()
    blob = json.dumps([chat.metadata(), chat.summary()])
    assert "sk-secret" not in blob
    assert chat.fingerprint in blob and len(chat.fingerprint) == 8
    assert chat.key == "sk-secret-value-abcdefghijklmnop"


def test_the_client_module_has_no_ungated_credential_path():
    """A structural check, because the bypass would be an import away.

    Checks the AST, not the text. The first version of this test grepped the source
    and failed on its own docstring -- the prose says "does NOT import pilot.llm".
    A test that reads prose cannot tell code from commentary, and prose is exactly
    where a bypass would NOT be. Imports and attribute names are what actually run.
    """
    import ast

    source = (ROOT / "runtime" / "planner" / "gated_chat.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)

    offenders = [m for m in imported
                 if m == "pilot" or m.startswith("pilot.")]
    assert not offenders, "the gated client imports the ungated client: %s" % offenders

    # The credential must come from the gate and from nowhere else. Look at what the
    # code REFERENCES and at the string literals it uses -- but exclude docstrings,
    # because prose explaining "we do not read the private key" must not read as
    # doing it. (The previous version of this test failed on its own explanation;
    # that is the same class of mistake as v1's docstring claiming an assertion it
    # did not have.)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))

    literals = {n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str)
                and id(n) not in docstrings}
    assert not any("FLEXCELL_PILOT_API_KEY" in s for s in literals)
    assert not any("deepseek_api_key" in s for s in literals)
    assert any("evobot_llm_key.sh" in s for s in literals), \
        "the gate path is not present as a literal; where does the key come from?"

    # And no bare name reference to the private key variable, in code or prose.
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "FLEXCELL_PILOT_API_KEY" not in names


# ------------------------------------------------------------ plan contract ----

def test_a_valid_two_move_plan_is_accepted():
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"},
                       {"object": "target_box_b", "zone": "zone_2"}],
             "unmoved": [], "confidence": "high"}
    validated, _, _ = ap.plan(_obs("T01"), StubChat(reply))
    assert [m["object"] for m in validated["moves"]] == ["target_box_a", "target_box_b"]


def test_an_unknown_object_is_fatal_and_nothing_is_dropped():
    """v1 FAILS this: it appended a problem and returned a shortened plan."""
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"},
                       {"object": "target_box_ZZZ", "zone": "zone_2"}],
             "unmoved": []}
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(_obs("T01"), StubChat(reply))
    assert any("unknown object" in p for p in err.value.problems)


def test_an_unknown_bin_is_fatal():
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_9"}], "unmoved": []}
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(_obs("T01"), StubChat(reply))
    assert any("unknown bin" in p for p in err.value.problems)


def test_a_relay_plan_with_via_is_accepted_and_expands_to_two_stages():
    """v1 FAILS this: its schema has no way to name the intermediate bin."""
    obs = _obs("T05")
    reply = {"moves": [{"object": "target_box_b", "zone": "zone_2",
                        "via": ["zone_1"]}], "unmoved": ["target_box_a"]}
    validated, _, _ = ap.plan(obs, StubChat(reply))
    assert validated["moves"][0]["via"] == ["zone_1"]
    scene = [{"name": z["name"], "pose": z["position"]} for z in obs["zones"]]
    composite = ap.to_composite_plan(scene, validated)
    assert [s["object_name"] for s in composite["stages"]] == ["target_box_b"] * 2
    assert composite["stages"][0]["place_pose"] == [0.12, -0.15, 0.0175]
    assert composite["stages"][1]["place_pose"] == [0.25, 0.05, 0.0175]


def test_a_via_that_repeats_the_destination_is_rejected():
    reply = {"moves": [{"object": "target_box_b", "zone": "zone_2",
                        "via": ["zone_2"]}], "unmoved": []}
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(_obs("T05"), StubChat(reply))
    assert any("not a relay" in p for p in err.value.problems)


# REMOVED, and the reason is recorded rather than the test quietly deleted.
#
# This slot used to hold test_an_object_planned_to_finish_in_two_bins_is_rejected,
# which asserted that two sequential moves for one object to two different bins must
# be REJECTED. That expectation was WRONG: it is the correct encoding of a revisit
# (T06: "put the block in the left bin, then move it on to the right bin").
#
# The test passed for as long as nothing exercised it, and a real 18-instance sweep
# found the cost: T06-train-seed1001 produced exactly this plan, the validator threw
# it away, and the run was recorded as a planning failure. The bug was in the
# validator AND in this test, which had codified the same mistake.
#
# The replacement below asserts what actually must be rejected. It is not a weaker
# test: "finish in two bins" was never the real invariant, "one final destination"
# is, and that is now stated directly and covered in both directions.
def test_two_sequential_moves_are_read_as_one_final_destination():
    """The invariant that replaced "an object may name only one bin".

    Sequential moves for one object are legal (revisit / relay). What must hold is
    that the plan has exactly ONE final destination per object -- the zone of the
    last move naming it -- which is what the evaluator grades.
    """
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"},
                       {"object": "target_box_a", "zone": "zone_2"}], "unmoved": []}
    validated, _, _ = ap.plan(_obs("T06"), StubChat(reply))

    final = {}
    for move in validated["moves"]:
        final[move["object"]] = move["zone"]
    assert final == {"target_box_a": "zone_2"}, final


def test_a_plan_longer_than_the_declared_budget_is_rejected():
    """v1 FAILS this: execution_budget.max_steps is never consulted."""
    obs = _obs("T01")
    obs["budget"] = {"max_steps": 2, "max_wall_s": 600.0}
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"},
                       {"object": "target_box_b", "zone": "zone_2"},
                       {"object": "target_box_a", "zone": "zone_2"}], "unmoved": []}
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(obs, StubChat(reply))
    assert any("budget" in p for p in err.value.problems)


def test_more_than_eight_moves_is_rejected_even_with_a_large_budget():
    obs = _obs("T01")
    obs["budget"] = {"max_steps": 40, "max_wall_s": 600.0}
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"}] * 9, "unmoved": []}
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(obs, StubChat(reply))
    assert any("limit is 8" in p for p in err.value.problems)


def test_an_identical_move_repeated_is_rejected():
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"}] * 2, "unmoved": []}
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(_obs("T01"), StubChat(reply))
    assert any("repeats" in p for p in err.value.problems)


def test_unmoved_naming_an_unknown_object_is_rejected():
    reply = {"moves": [{"object": "target_box_a", "zone": "zone_1"}],
             "unmoved": ["target_box_ZZZ"]}
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(_obs("T02"), StubChat(reply))
    assert any("unmoved names unknown" in p for p in err.value.problems)


def test_json_inside_a_code_fence_is_parsed():
    fenced = "```json\n" + json.dumps(
        {"moves": [{"object": "target_box_a", "zone": "zone_1"}], "unmoved": []}) + "\n```"
    validated, _, _ = ap.plan(_obs("T01"), StubChat(fenced))
    assert validated["moves"][0]["object"] == "target_box_a"


def test_garbage_raises_rather_than_silently_passing():
    with pytest.raises(ValueError):
        ap.plan(_obs("T01"), StubChat("I think the red block should go left."))


def test_composite_conversion_takes_only_positions_from_the_scene():
    obs = _obs("T01")
    scene = [{"name": z["name"], "pose": z["position"]} for z in obs["zones"]]
    composite = ap.to_composite_plan(
        scene, {"moves": [{"object": "target_box_a", "zone": "zone_2"}]})
    assert composite["stages"][0]["place_pose"] == [0.25, 0.05, 0.0175]
    assert composite["stages"][0]["object_name"] == "target_box_a"

# --------------------------------------------------------------- harness ----

import run_baseline_b as hb


@pytest.mark.parametrize("path", [
    ROOT / "benchmark" / "held_out" / "public" / "HO-008a467cde3f.json",
    ROOT / "benchmark" / "evaluators" / "evaluate.py",
    ROOT / "benchmark" / "evaluators",
    ROOT / "benchmark" / "held_out",
])
def test_the_harness_refuses_to_read_answer_bearing_paths(path):
    """The isolation rule from benchmark/README.md, enforced in code not prose."""
    with pytest.raises(hb.IsolationError):
        hb.assert_not_forbidden(path)


def test_the_harness_allows_the_public_train_split():
    assert hb.assert_not_forbidden(TRAIN / "T01-train-seed1000.json") is True


def test_the_isolation_guard_cannot_be_fooled_by_a_relative_path():
    import os
    relative = os.path.relpath(str(ROOT / "benchmark" / "held_out" / "public"),
                               str(ROOT))
    with pytest.raises(hb.IsolationError):
        hb.assert_not_forbidden(relative)


def test_a_dry_run_makes_no_model_call_and_emits_the_prompt(tmp_path):
    """A dry run must be free. If it ever calls out, this fails loudly."""
    class Exploding:
        def chat(self, messages):
            raise AssertionError("a dry run must not call the model")

        def metadata(self):
            return {}

    result = hb.run_one(TRAIN / "T01-train-seed1000.json", tmp_path, dry=True)
    assert result["stage"] == "dry"
    assert result["tokens"] == 0
    assert (tmp_path / "prompt.txt").exists()
    assert "Task instruction" in (tmp_path / "prompt.txt").read_text(encoding="utf-8")
    assert not (tmp_path / "plan.json").exists(), "a dry run must not emit a plan"


def test_the_harness_builds_an_executable_plan_from_a_stubbed_reply(tmp_path):
    """End to end with the model stubbed: observation -> plan -> plan.json."""
    class Stub:
        def chat(self, messages):
            return {"content": json.dumps({
                "moves": [{"object": "target_box_a", "zone": "zone_1"},
                          {"object": "target_box_b", "zone": "zone_2"}],
                "unmoved": [], "confidence": "high"}),
                "tokens": 0, "seconds": 0.0, "model": "stub"}

        def metadata(self):
            return {"key_fingerprint": "deadbeef"}

        def summary(self):
            return {"calls": 1, "tokens": 0}

    result = hb.run_one(TRAIN / "T01-train-seed1000.json", tmp_path, chat=Stub())
    assert result["planned"] is True
    plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))

    # The RunComposite contract, checked here rather than discovered on the robot.
    assert set(plan) == {"task_id", "initial_objects", "stages", "final_empty_positions",
                         "position_tolerance_m", "clearance_m", "motion_profile_id"}
    assert 1 <= len(plan["stages"]) <= 8
    assert 0.05 <= plan["clearance_m"] <= 0.25
    assert 0 < plan["position_tolerance_m"] <= 0.06
    assert len({s["stage_id"] for s in plan["stages"]}) == len(plan["stages"])
    for stage in plan["stages"]:
        assert set(stage) >= {"stage_id", "object_name", "place_pose"}
        assert len(stage["place_pose"]) == 3
    # every declared object must be present in initial_objects, or the composite
    # rejects the plan with "plan must declare every observed object"
    declared = {o["name"] for o in json.loads(
        (TRAIN / "T01-train-seed1000.json").read_text(encoding="utf-8"))["objects"]}
    assert {o["object_name"] for o in plan["initial_objects"]} == declared


def test_a_relay_task_produces_two_stages_for_the_same_object(tmp_path):
    class Stub:
        def chat(self, messages):
            return {"content": json.dumps({
                "moves": [{"object": "target_box_b", "zone": "zone_2",
                          "via": ["zone_1"]}],
                "unmoved": ["target_box_a"], "confidence": "high"}),
                "tokens": 0, "seconds": 0.0, "model": "stub"}

        def metadata(self):
            return {"key_fingerprint": "deadbeef"}

        def summary(self):
            return {"calls": 1, "tokens": 0}

    result = hb.run_one(TRAIN / "T05-train-seed1000.json", tmp_path, chat=Stub())
    assert result["planned"] is True
    plan = json.loads((tmp_path / "plan.json").read_text(encoding="utf-8"))
    names = [s["object_name"] for s in plan["stages"]]
    assert names == ["target_box_b", "target_box_b"], names

# ------------------------------------- regressions from a real 18-instance sweep ----

def test_a_revisit_encoded_as_two_sequential_moves_is_ACCEPTED():
    """REGRESSION, found by a real run, not by reasoning.

    T06-train-seed1001 instruction: "put the red block in the left bin, then move it
    on to the right bin. Only the final position counts." The model answered with two
    sequential moves for the same object. That is a CORRECT encoding of a revisit,
    and the first version of this validator rejected it because it collected every
    zone per object into a set and demanded exactly one member.

    A validator that rejects a correct plan is a false negative, and it is worse than
    a false positive here: it silently converts a planning success into a planning
    failure, which is the direction that flatters nobody but destroys the measurement.
    """
    obs = _obs("T06", 1000)
    reply = {"moves": [{"object": "target_box_b", "zone": "zone_2"},
                       {"object": "target_box_b", "zone": "zone_1"}],
             "unmoved": ["target_box_a"]}
    validated, _, _ = ap.plan(obs, StubChat(reply))
    assert [m["zone"] for m in validated["moves"]] == ["zone_2", "zone_1"]


def test_a_revisit_encoded_as_one_move_with_via_is_also_ACCEPTED():
    """The other legal encoding of the SAME instruction must also pass."""
    obs = _obs("T06", 1000)
    reply = {"moves": [{"object": "target_box_b", "zone": "zone_1",
                        "via": ["zone_2"]}],
             "unmoved": ["target_box_a"]}
    validated, _, _ = ap.plan(obs, StubChat(reply))
    assert validated["moves"][0]["zone"] == "zone_1"
    assert validated["moves"][0]["via"] == ["zone_2"]


def test_both_encodings_produce_the_same_final_destination():
    """The equivalence that makes both encodings legal, checked rather than assumed."""
    obs = _obs("T06", 1000)
    sequential, _, _ = ap.plan(obs, StubChat({"moves": [
        {"object": "target_box_b", "zone": "zone_2"},
        {"object": "target_box_b", "zone": "zone_1"}], "unmoved": []}))
    via, _, _ = ap.plan(obs, StubChat({"moves": [
        {"object": "target_box_b", "zone": "zone_1", "via": ["zone_2"]}], "unmoved": []}))

    scene = [{"name": z["name"], "pose": z["position"]} for z in obs["zones"]]
    stages_seq = ap.to_composite_plan(scene, sequential)["stages"]
    stages_via = ap.to_composite_plan(scene, via)["stages"]
    assert [s["place_pose"] for s in stages_seq] == [s["place_pose"] for s in stages_via]
    assert [s["object_name"] for s in stages_seq] == [s["object_name"] for s in stages_via]


def test_routing_through_the_final_destination_is_rejected_as_wasted_motion():
    reply = {"moves": [{"object": "target_box_b", "zone": "zone_1",
                        "via": ["zone_1"]}], "unmoved": []}
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(_obs("T05", 1000), StubChat(reply))
    assert any("not a relay" in p or "changes nothing" in p
               for p in err.value.problems)


def test_a_rejection_keeps_the_raw_reply_as_evidence():
    """A rejection without the model's words cannot be told from a model error."""
    bad = json.dumps({"moves": [{"object": "GHOST", "zone": "zone_1"}], "unmoved": []})
    with pytest.raises(ap.PlanRejected) as err:
        ap.plan(_obs("T01", 1000), StubChat(bad))
    assert getattr(err.value, "raw_reply", "") == bad


def test_the_harness_writes_the_raw_reply_even_when_the_plan_is_rejected(tmp_path):
    class BadStub:
        def chat(self, messages):
            return {"content": json.dumps({
                "moves": [{"object": "GHOST", "zone": "zone_1"}], "unmoved": []}),
                "tokens": 11, "seconds": 0.1, "model": "stub"}

        def metadata(self):
            return {"key_fingerprint": "deadbeef"}

    result = hb.run_one(TRAIN / "T01-train-seed1000.json", tmp_path, chat=BadStub())
    assert result["planned"] is False
    written = json.loads((tmp_path / "agent_reply.json").read_text(encoding="utf-8"))
    assert written["raw_reply"], "the raw reply was discarded -- failure is now unfalsifiable"
    assert "GHOST" in written["raw_reply"]
    assert not (tmp_path / "plan.json").exists()

# ---------------------- real model replies, captured verbatim from a live run ----

# These two replies are the ACTUAL bytes the model returned for the same task
# (T06-train-seed1001, "put the red block in the left bin, then move it on to the
# right bin") on two different calls at temperature 0. They differ. That is worth
# recording: this API is not deterministic at temperature 0, so a baseline that
# reports a single run per instance is reporting one sample of a distribution.
# Captured VERBATIM from a live call, stored as a Python string literal produced by
# json.dumps() so no hand-transcription error can enter the fixture. (The first
# version of this fixture was hand-typed from a truncated print and was not valid
# JSON -- the test failed on the FIXTURE, which is the right way round but still
# wasted a cycle. Never reconstruct a captured reply by hand.)
REAL_REPLY_VIA = (
    '{"moves":[{"object":"target_box_a","zone":"zone_1","via":["zone_2"],'
    '"why":"Red block goes to left bin first, then final right bin."}],'
    '"unmoved":["target_box_b"],"confidence":"high","uncertainty":""}'
)

# The SEQUENTIAL encoding of the same instruction. Also a real shape: it is what the
# model returned on a different call for this task, and it is the shape the first
# validator wrongly rejected.
REAL_REPLY_SEQUENTIAL = (
    '{"moves":[{"object":"target_box_a","zone":"zone_2",'
    '"why":"Red block to left bin (zone_2 has +y/left position)."},'
    
    '{"object":"target_box_a","zone":"zone_1",'
    '"why":"Then move red block to right bin (zone_1)."}],'
    '"unmoved":["target_box_b"],"confidence":"high"}'
)


def test_both_real_model_encodings_of_T06_are_accepted():
    """Both of these were really returned by the model for the same task.

    The first version of the validator accepted only the via form and silently
    discarded the sequential form, turning a correct plan into a recorded planning
    failure. Real data, not a constructed edge case.
    """
    obs = _obs("T06", 1001)
    validated, _, _ = ap.plan(obs, StubChat(REAL_REPLY_SEQUENTIAL))
    assert [m["zone"] for m in validated["moves"]] == ["zone_2", "zone_1"]

    validated_via, _, _ = ap.plan(obs, StubChat(REAL_REPLY_VIA))
    assert validated_via["moves"][0]["zone"] == "zone_1"
    assert validated_via["moves"][0]["via"] == ["zone_2"]


def test_an_empty_model_reply_fails_loudly_and_is_recorded(tmp_path):
    """A transport-level empty answer must be a recorded failure, never a silent pass.

    Observed live: one call returned content="" after consuming 2625 tokens. The
    correct behaviour is to reject it and to WRITE that fact down, because an empty
    reply is indistinguishable from a lost one unless it is on disk.
    """
    class EmptyStub:
        def chat(self, messages):
            return {"content": "", "tokens": 2625, "seconds": 11.1, "model": "stub"}

        def metadata(self):
            return {"key_fingerprint": "deadbeef"}

    result = hb.run_one(TRAIN / "T06-train-seed1001.json", tmp_path, chat=EmptyStub())
    assert result["planned"] is False
    written = json.loads((tmp_path / "agent_reply.json").read_text(encoding="utf-8"))
    assert written["problems"], "an empty reply must carry a problem"
    assert written["usage"]["tokens"] == 2625, "the spend must still be recorded"
    assert not (tmp_path / "plan.json").exists()
