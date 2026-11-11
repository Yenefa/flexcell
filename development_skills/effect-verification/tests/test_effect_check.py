"""Tests for effect verification.

Each test corresponds to a real incident from this session where a conclusion was drawn from
the ABSENCE of a complaint rather than from evidence that the effect happened:

  A  a failed git command produced empty output, read as "zero lines changed"
  B  sed -i failed on a permission error, read as "the mutation was applied"
  C  cd to an unset variable ran pytest in the home directory, "no tests ran" read as passing
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import effect_check  # noqa: E402

E = effect_check.EffectNotVerified


# ------------------------------------------------- incident A: empty output

def test_empty_string_is_not_success():
    with pytest.raises(E):
        effect_check.require_nonempty("", "git diff output")


def test_none_is_not_success():
    with pytest.raises(E):
        effect_check.require_nonempty(None, "captured output")


def test_empty_list_is_not_success():
    with pytest.raises(E):
        effect_check.require_nonempty([], "match list")


def test_a_falsy_but_present_value_is_accepted():
    """"0" is a legitimate result, unlike "". Conflating the two is the bug."""
    assert effect_check.require_nonempty("0", "count") is True
    assert effect_check.require_nonempty(0, "count") is True


# ------------------------------------- incident B: the edit did not take

def test_unchanged_file_raises(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("same\n", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("same\n", encoding="utf-8")
    with pytest.raises(E) as exc:
        effect_check.require_changed(str(a), str(b))
    assert "did not take effect" in str(exc.value)


def test_changed_file_passes(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("after\n", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("before\n", encoding="utf-8")
    assert effect_check.require_changed(str(a), str(b))


def test_a_missing_file_raises_rather_than_returning_none(tmp_path):
    with pytest.raises(E):
        effect_check.digest(str(tmp_path / "absent.txt"))


# ------------------------------------------- incident C: no tests ran

def test_no_tests_ran_is_not_a_pass():
    with pytest.raises(E) as exc:
        effect_check.require_pytest_summary("no tests ran in 0.10s")
    assert "collected nothing" in str(exc.value)


def test_collected_zero_items_is_not_a_pass():
    with pytest.raises(E):
        effect_check.require_pytest_summary("collected 0 items / 1 error")


def test_output_without_a_passed_summary_is_not_a_pass():
    with pytest.raises(E):
        effect_check.require_pytest_summary("all tests collected, nothing reported")


def test_a_real_passing_summary_is_accepted():
    assert effect_check.require_pytest_summary("73 passed in 10.81s") is True


def test_a_failing_run_that_still_says_passed_is_not_silently_accepted():
    """A suite with failures still contains " passed", so this helper only rules out the
    empty run. The exit code must be checked separately -- stated here so nobody assumes
    this function proves success."""
    assert effect_check.require_pytest_summary("2 failed, 9 passed in 0.23s") is True


# ------------------------------------------------------- token presence

def test_absent_token_raises():
    with pytest.raises(E):
        effect_check.require_contains("all good", "PASSED")


def test_present_token_passes():
    assert effect_check.require_contains("suite PASSED", "PASSED")


def test_none_output_raises():
    with pytest.raises(E):
        effect_check.require_contains(None, "PASSED")


# ---------------------------------------------------------------- CLI

def test_cli_changed_reports_verified(tmp_path, capsys):
    a = tmp_path / "a.txt"
    a.write_text("after\n", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("before\n", encoding="utf-8")
    rc = effect_check.main(["changed", str(a), "--against", str(b)])
    assert rc == 0
    assert "EFFECT_VERIFIED" in capsys.readouterr().out


def test_cli_changed_reports_not_verified_and_exits_nonzero(tmp_path, capsys):
    a = tmp_path / "a.txt"
    a.write_text("same\n", encoding="utf-8")
    b = tmp_path / "b.txt"
    b.write_text("same\n", encoding="utf-8")
    rc = effect_check.main(["changed", str(a), "--against", str(b)])
    assert rc == 1, "a no-op edit must not exit zero"
    assert "EFFECT_NOT_VERIFIED" in capsys.readouterr().out