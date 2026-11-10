#!/usr/bin/env python3
"""Held-out sealing tests: the public side must carry no answer at all."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark" / "generators"))

import generate as gen
import seal_held_out as seal

SALT = "unit-test-salt"


def test_split_removes_every_answer_field_from_the_public_side():
    for template in gen.TEMPLATES:
        spec = gen.generate(template, 9000, "held_out")
        oid, public, sealed = seal.split_spec(spec, SALT)
        seal.assert_public_is_clean(public)
        assert "expected_goal" not in public
        assert "constraints" not in public
        assert "template_id" not in public
        assert "random_seed" not in public
        assert oid.startswith("HO-")


def test_the_sealed_side_keeps_everything_needed_to_grade():
    spec = gen.generate("T05_relay", 9000, "held_out")
    oid, public, sealed = seal.split_spec(spec, SALT)
    assert sealed["expected_goal"] == spec["expected_goal"]
    assert sealed["template_id"] == spec["template_id"]
    assert sealed["random_seed"] == spec["random_seed"]
    assert sealed["public_task_id"] == oid


def test_public_plus_sealed_reconstructs_the_full_spec():
    spec = gen.generate("T02_exclusion", 9001, "held_out")
    oid, public, sealed = seal.split_spec(spec, SALT)
    rebuilt = dict(public)
    for key in ("expected_goal", "constraints", "template_id", "random_seed",
                "instance_sha256"):
        rebuilt[key] = sealed[key]
    # the only differences are the intentionally opaque id and the recorded original
    assert rebuilt["expected_goal"] == spec["expected_goal"]
    assert rebuilt["instruction"] == spec["instruction"]


def test_public_task_id_does_not_reveal_template_or_seed():
    oid, _, _ = seal.split_spec(gen.generate("T01_multi_object_sorting", 9000), SALT)
    assert "seed" not in oid.lower()
    assert "T01" not in oid
    assert "9000" not in oid


def test_same_spec_with_a_different_salt_gets_a_different_id():
    spec = gen.generate("T01_multi_object_sorting", 9000)
    a, _, _ = seal.split_spec(spec, "salt-a")
    b, _, _ = seal.split_spec(spec, "salt-b")
    assert a != b


def test_a_public_file_that_leaks_the_answer_is_rejected():
    import pytest
    bad = {"task_id": "HO-abc", "instruction": "do it", "objects": [], "zones": [],
           "evaluator_version": "0.1.0", "execution_budget": {}, "split": "held_out",
           "expected_goal": {"placement": {"a": "zone_1"}}}
    with pytest.raises(AssertionError):
        seal.assert_public_is_clean(bad)

