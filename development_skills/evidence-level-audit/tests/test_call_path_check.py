"""Tests for the call-path check.

The check exists because a verifier passing its own tests proves nothing about whether it
runs. These tests use temporary trees so they never depend on the real repository layout.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import call_path_check  # noqa: E402


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_a_referencing_file_is_counted(tmp_path):
    _write(tmp_path, "caller.py", "from verify import verify\nverify(x)\n")
    hits, misses = call_path_check.callers_of("verify", call_path_check.files_under(str(tmp_path)))
    assert len(hits) == 1
    assert misses == []


def test_a_non_referencing_file_is_reported(tmp_path):
    _write(tmp_path, "other.py", "print('nothing here')\n")
    hits, misses = call_path_check.callers_of("verify", call_path_check.files_under(str(tmp_path)))
    assert hits == []
    assert len(misses) == 1


def test_the_symbol_absent_everywhere_fails_the_cli(tmp_path, capsys):
    _write(tmp_path, "a.py", "pass\n")
    _write(tmp_path, "b.sh", "echo hi\n")
    rc = call_path_check.main(["--symbol", "verify", "--expect-caller", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "ABSENT" in out


def test_the_symbol_present_passes_the_cli(tmp_path, capsys):
    _write(tmp_path, "a.py", "import verify\n")
    rc = call_path_check.main(["--symbol", "verify", "--expect-caller", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK" in out


def test_markdown_counts_as_a_reference(tmp_path):
    """Documentation mentioning a symbol is NOT a caller, but the tool is deliberately
    literal: it reports references. The distinction is enforced by the reviewer, and this
    test pins the behaviour so the tool does not silently start pretending otherwise."""
    _write(tmp_path, "notes.md", "we should call verify someday\n")
    hits, _ = call_path_check.callers_of("verify", call_path_check.files_under(str(tmp_path)))
    assert len(hits) == 1


def test_an_empty_directory_is_not_a_pass(tmp_path, capsys):
    rc = call_path_check.main(["--symbol", "verify", "--expect-caller", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1, "an empty scan must not report success"
    assert "EMPTY" in out
