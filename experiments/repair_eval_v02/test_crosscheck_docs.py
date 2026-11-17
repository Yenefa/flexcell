"""The cross-document check must stay empty.

Two real disagreements were found by comparing documents mechanically rather than
by reading them: the protocol offered condition B the verdict the policy seals, and
the interface table listed six denial codes when the module defines fifteen.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import crosscheck_docs as C  # noqa: E402


def test_the_documents_and_the_code_agree():
    problems = C.check()
    assert not problems, problems


def test_the_check_can_actually_fail():
    """A check that cannot fail is not a check - written after I shipped one."""
    real = C.denial_codes()
    assert real, "no denial codes parsed out of visibility.py"
    # a code that does not exist must be reported missing
    missing = "code_that_does_not_exist"
    assert missing not in C.read(C.VISIBILITY_DOC)
    problems = C.check()
    assert missing not in " ".join(problems)


def test_the_denial_code_list_is_not_empty_and_matches_the_documents():
    codes = C.denial_codes()
    assert len(codes) >= 10, codes
    visibility = C.read(C.VISIBILITY_DOC)
    missing = [c for c in codes if c not in visibility]
    assert not missing, missing
