"""Tests for safe pkill patterns.

The two incidents these guard against: a whole-name bracket that became a character class
and matched 4 of 4 unrelated lines, and a cleanup that reported success while 136 orphans
survived. Both are string/arithmetic facts, testable without spawning processes.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import pytest

import safe_pattern  # noqa: E402


def test_the_bracket_wraps_exactly_one_character():
    assert safe_pattern.safe_pattern("carry_server") == "[c]arry_server"


def test_the_pattern_does_not_match_itself():
    """The whole point of the trick: pkill must not select its own command line."""
    pattern = safe_pattern.safe_pattern("carry_server")
    literal = "pkill -9 -f " + pattern
    import re
    assert re.search(pattern, "carry_server") is not None
    assert re.search(pattern, pattern) is None, "pattern would match itself"


def test_the_incident_pattern_is_rejected_as_hazardous():
    """The real mistake: [carry_server] is a character class."""
    assert safe_pattern.is_hazardous("[carry_server]") is True


def test_the_correct_pattern_is_not_hazardous():
    assert safe_pattern.is_hazardous("[c]arry_server") is False


def test_the_hazardous_pattern_matches_junk_the_safe_one_does_not():
    """Measured in this session: 4 of 4 unrelated lines matched the bad pattern."""
    import re
    bad = "[carry_server]"
    good = "[c]arry_server"
    junk = ["ros2 launch other_pkg", "python3 serve.py", "gz sim empty.sdf", "node worker"]
    assert sum(1 for line in junk if re.search(bad, line)) == 4
    assert sum(1 for line in junk if re.search(good, line)) == 0


def test_an_empty_name_is_refused():
    with pytest.raises(ValueError):
        safe_pattern.safe_pattern("")


def test_a_name_that_is_already_bracketed_is_refused():
    with pytest.raises(ValueError):
        safe_pattern.safe_pattern("[c]arry_server")


def test_the_safe_count_threshold_is_a_real_number():
    """A cleanup that reports success on a huge match count is the failure mode."""
    assert safe_pattern.MAX_SAFE_MATCHES == 40
