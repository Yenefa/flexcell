"""Canonical error taxonomy + legacy mapping (M2.2-1, issue #20).

Values are REUSED from the legacy per-action constants wherever the legacy
numbers are already consistent across skills (21 = object not found,
23/25/30 skill-specific failures, 32/41 universal) - so canonical codes are
backward compatible by construction.  Only genuinely missing concepts get
new numbers (VERIFY_FAILED 26, TIMEOUT 33, STALE_WORLD 34, SAFETY_REJECTED
35).  Task-level codes (ERR_SKILL_FAILED 50, ERR_RECOVERY_EXHAUSTED 51) are
deliberately outside the skill taxonomy.

Fail-closed: an unmapped (skill, legacy code, outcome) pair canonicalizes
to ERR_INTERNAL with a mapping_warning - an unnamed semantic is never
passed through to a policy.

STALE_WORLD / SAFETY_REJECTED are vocabulary-only this round: their
emission points land with the safety gate (issue #6), per the ratified
order.  STATUS_SKIPPED likewise has no emitter yet (honest vocabulary).
"""

# ---------------------------------------------------------------- canonical codes
ERR_OK = 0
ERR_INVALID_GOAL = 1
ERR_INTERNAL = 2
ERR_IK_UNREACHABLE = 10
ERR_OBJECT_NOT_FOUND = 21          # legacy name: ERR_OBJECT_UNKNOWN (same value everywhere)
ERR_WORLD_STATE_UNAVAILABLE = 22   # legacy: Observe used 3 - mapped here
ERR_GRASP_FAILED = 23
ERR_NOT_CARRIED = 24
ERR_PLACE_FAILED = 25
ERR_VERIFY_FAILED = 26             # canonical view of a verify MISMATCH (legacy code stays 0)
ERR_MOTION_FAILED = 30
ERR_CANCELED = 32
ERR_TIMEOUT = 33                   # executor plumbing failures (sentinel -1 / outcome 255)
ERR_STALE_WORLD = 34               # vocabulary only; emission lands with the #6 gate
ERR_SAFETY_REJECTED = 35           # vocabulary only; emission lands with the #6 gate
ERR_RESOURCE_BUSY = 41
ERR_SKILL_CONTRACT_VIOLATION = 52  # executor post-condition rejection (M2.2-0)

# ---------------------------------------------------------------- status vocabulary
STATUS_NONE = 0       # default-constructed result: never passed finish() - phantom fingerprint
STATUS_SUCCESS = 1
STATUS_FAILURE = 2
STATUS_SKIPPED = 3    # vocabulary only this round; no emitter yet
STATUS_CANCELED = 4   # outcome=2 must not masquerade as FAILURE (chief-approved 4th value)

# ---------------------------------------------------------------- plumbing sentinels
PLUMBING_ERROR_CODE = -1   # task_fsm records -1 when no typed skill result exists
PLUMBING_OUTCOME = 255     # decision_policy.OUTCOME_NONE

# ---------------------------------------------------------------- task-level codes
# Task-level codes are deliberately outside the skill taxonomy: they live on
# RunDemo/RunPickPlace results and are produced by the EXECUTOR, not by any
# skill server.  50/51 reuse the legacy values.
TASK_ERR_SKILL_FAILED = 50
TASK_ERR_RECOVERY_EXHAUSTED = 51

# FSMPolicy ABORT reason codes (decision_policy.py RC_*) that mean "a recovery
# budget is spent".  The executor maps policy ABORT decisions to typed task
# codes through task_abort_error_code instead of degenerating into the
# catch-all PolicyStateError path (M2.3 audit P1-2: the typed semantics were
# silently lost when the policy seam landed - 87c_exhaust recorded
# ERR_SKILL_FAILED + "policy state error" where ERR_RECOVERY_EXHAUSTED was
# the frozen meaning).
_BUDGET_ABORT_REASONS = frozenset(('BUDGET_EXHAUSTED', 'VERIFY_BUDGET_EXHAUSTED'))


def task_abort_error_code(reason_code):
    """Policy ABORT decision -> typed task-level error code.

    BUDGET_EXHAUSTED / VERIFY_BUDGET_EXHAUSTED -> ERR_RECOVERY_EXHAUSTED;
    everything else (NON_RECOVERABLE, OBSERVE_FAILED, unknown) fails closed
    to ERR_SKILL_FAILED.
    """
    return (TASK_ERR_RECOVERY_EXHAUSTED if reason_code in _BUDGET_ABORT_REASONS
            else TASK_ERR_SKILL_FAILED)


_SKILLS = ('OBSERVE', 'PICK', 'PLACE', 'VERIFY')

# (legacy error_code, outcome-or-None) -> canonical;  None outcome = any outcome.
# Verify carries outcome context: (0, 0) is VERIFIED=OK while (0, 1) is MISMATCH
# -> ERR_VERIFY_FAILED (legacy error_code stays 0 for compatibility).
_OBSERVE_MAP = {
    (0, 0): ERR_OK,
    (2, None): ERR_INTERNAL,
    (3, None): ERR_WORLD_STATE_UNAVAILABLE,
    (32, None): ERR_CANCELED,      # OUTCOME_CANCELED (audit P0-3 cancel semantics)
}
_PICK_MAP = {
    (0, 0): ERR_OK,
    (1, None): ERR_INVALID_GOAL,
    (2, None): ERR_INTERNAL,
    (10, None): ERR_IK_UNREACHABLE,
    (21, None): ERR_OBJECT_NOT_FOUND,
    (22, None): ERR_WORLD_STATE_UNAVAILABLE,
    (23, None): ERR_GRASP_FAILED,
    (30, None): ERR_MOTION_FAILED,
    (32, None): ERR_CANCELED,
    (41, None): ERR_RESOURCE_BUSY,
}
_PLACE_MAP = dict(_PICK_MAP)
_PLACE_MAP.update({
    (24, None): ERR_NOT_CARRIED,
    (25, None): ERR_PLACE_FAILED,
})
_VERIFY_MAP = {
    (0, 0): ERR_OK,
    (0, 1): ERR_VERIFY_FAILED,
    (2, None): ERR_INTERNAL,
    (21, None): ERR_OBJECT_NOT_FOUND,
    (22, None): ERR_WORLD_STATE_UNAVAILABLE,
    (32, None): ERR_CANCELED,      # OUTCOME_CANCELED=3 (audit P0-3 cancel semantics)
}
_MAPS = {
    'OBSERVE': _OBSERVE_MAP,
    'PICK': _PICK_MAP,
    'PLACE': _PLACE_MAP,
    'VERIFY': _VERIFY_MAP,
}


def canonicalize(skill, error_code, outcome):
    """(skill, legacy error_code, outcome) -> (canonical_code, mapping_warning).

    outcome=None matches any outcome for that legacy code.  Plumbing
    sentinels (error_code -1) map to ERR_TIMEOUT - the specific reason
    stays in the record's detail.  Unknown pairs fail closed to
    ERR_INTERNAL with a mapping_warning string (never silent).
    """
    code = int(error_code)
    if code == PLUMBING_ERROR_CODE:
        return ERR_TIMEOUT, None
    out = None if outcome is None else int(outcome)
    table = _MAPS.get(skill)
    if table is None:
        return ERR_INTERNAL, 'unknown skill %r' % (skill,)
    if (code, out) in table:
        return table[(code, out)], None
    if (code, None) in table:
        return table[(code, None)], None
    return (ERR_INTERNAL,
            'unmapped legacy (error_code=%d, outcome=%s) from %s' % (code, out, skill))


def status_from_outcome(skill, outcome):
    """outcome -> status.  THE single derivation rule for finish().

    Asymmetry note: outcome=2 means CANCELED for OBSERVE/PICK/PLACE; VERIFY
    (vocabulary VERIFIED/MISMATCH/FAILED/CANCELED) cancels on outcome=3.
    """
    o = int(outcome)
    if skill == 'VERIFY':
        if o == 0:
            return STATUS_SUCCESS
        if o == 3:
            return STATUS_CANCELED     # OUTCOME_CANCELED (added with P0-3)
        return STATUS_FAILURE          # MISMATCH(1) / FAILED(2)
    if o == 0:
        return STATUS_SUCCESS
    if o == 2:
        return STATUS_CANCELED
    if o == PLUMBING_OUTCOME:
        return STATUS_NONE             # plumbing: no skill verdict exists
    return STATUS_FAILURE
