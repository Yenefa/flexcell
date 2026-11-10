#!/usr/bin/env python3
"""The B/C pair must differ ONLY by the experience channel."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in ("runtime/planner", "experiments/baselines", "evolution/experience"):
    sys.path.insert(0, str(ROOT / p))

import agent_planner as ap
import baseline_c as C
import store


def _obs():
    return {"instruction": "Move the blue block to the left bin, passing through the right bin first.",
            "objects": [{"name": "target_box_a", "color": "red", "position": [0.22, 0.0, 0.0175]}],
            "zones": [{"name": "zone_1", "position": [0.12, -0.15, 0.0175], "radius": 0.06}],
            "skills": ["pick", "place"]}


def test_experience_enrichment_adds_no_answer_fields():
    obs = _obs()
    lessons = [{"lesson": "Two objects sent to the same bin need distinct landing spots inside it.",
                "failure_class": "planning", "source_run": "run-x"}]
    enriched = dict(obs, experience=lessons)
    blob = json.dumps(enriched).lower()
    for banned in ["expected_goal", "placement", "unmoved", "random_seed",
                   "evaluator", "tolerance", "threshold"]:
        assert banned not in blob, banned


def test_c_prompt_contains_the_lessons_and_b_prompt_does_not():
    obs = _obs()
    _, user_b = ap.build_prompt(obs)
    enriched = dict(obs, experience=[{"lesson": "allow a bounded admission wait",
                                     "failure_class": "runtime"}])
    _, user_c = ap.build_prompt(enriched)
    assert "Validated lessons" not in user_b
    assert "Validated lessons" in user_c
    assert "allow a bounded admission wait" in user_c
    # everything else is identical
    assert user_b.split("Task instruction:")[1] == user_c.split("Task instruction:")[1]


def test_system_prompt_is_identical_for_b_and_c():
    obs = _obs()
    s_b, _ = ap.build_prompt(obs)
    s_c, _ = ap.build_prompt(dict(obs, experience=[{"lesson": "x"}]))
    assert s_b == s_c


def test_store_scope_guard_rejects_answer_shaped_lessons():
    import pytest
    for bad in ["put box_a in zone_1 to pass the evaluator",
                "the acceptance tolerance is 0.06",
                "expected_goal says zone_2"]:
        with pytest.raises(ValueError):
            store.make_record("t", "planning", {"error_code": 1}, bad, "run", "failed")

