"""SkillResult v2 helpers (M2.2-1): the single derivation point for `status`.

Every skill server assigns `res.status` exactly once, inside its finish()
path, via `derive_status` - no scattered per-branch assignments.  The
module also shapes `previous_skill_result` for the decision log: the
additive, policy-facing view of the skill result the next decision reacts
to (status + legacy code + canonical code, with a mapping_warning when the
fail-closed branch fired).
"""

from flexcell_skills.contracts.error_codes import (
    PLUMBING_ERROR_CODE, PLUMBING_OUTCOME, canonicalize, status_from_outcome)


def derive_status(skill, outcome):
    """status for one finished skill invocation (finish() calls this once)."""
    return status_from_outcome(skill, outcome)


def previous_skill_result(action, outcome, error_code):
    """Shape the last executed skill result for a decision-log record.

    action: ACTION_* name (OBSERVE/PICK/PLACE/VERIFY); outcome and
    error_code: the raw legacy ints from the executor's HistoryRecord.
    Returns the additive dict; carries mapping_warning when canonicalize
    failed closed.
    """
    o = int(outcome)
    code = int(error_code)
    status = status_from_outcome(action, o)
    if code == PLUMBING_ERROR_CODE and o == PLUMBING_OUTCOME:
        canonical, warning = canonicalize(action, code, None)
    else:
        canonical, warning = canonicalize(action, code, o)
    d = {
        'skill': action,
        'status': int(status),
        'error_code': code,
        'canonical_error_code': int(canonical),
    }
    if warning is not None:
        d['mapping_warning'] = warning
    return d
