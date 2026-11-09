"""Recovery eligibility predicate (M2.2-2, issue #21): the frozen Week-1.5
recovery semantics extracted as a named pure function.

`recovery_eligible` answers exactly one question: "is THIS failure the kind
the bounded recovery recipe can plausibly fix?"  It classifies eligibility
only - the attempt-vs-budget counting stays with the policy that owns the
recovery budget (FSMPolicy), and the executor stays the sole dispatcher.

Frozen eligibility, verbatim from the Week-1.5 semantics that FSMPolicy
replays:
- PICK:   a typed failure (not a plumbing sentinel) whose legacy code is in
          RECOVERABLE_PICK_ERRORS {22, 23, 30}.  Object-not-found (21) is
          deliberately NOT recoverable.
- VERIFY: any non-success outcome (mismatch, failure, even plumbing - the
          re-verify decides; the reobserve result is ignored, frozen).
- PLACE / OBSERVE: never recoverable (failures abort; a carried box is not
  retried).

Recipes are audit-facing names: PICK -> REOBSERVE+RETRY, VERIFY ->
REOBSERVE+REVERIFY.  Recovery trajectories enter the audit log (the
decision log's recovery block) but never the policy context: policies see
only HistoryRecord.
"""

from flexcell_skills.contracts.error_codes import PLUMBING_OUTCOME

ACTION_PICK = 'PICK'
ACTION_VERIFY = 'VERIFY'

RECOVERY_REOBSERVE = 'REOBSERVE'
RECOVERY_RETRY = 'RETRY'
RECOVERY_ABORT = 'ABORT'

RECIPE_PICK = 'REOBSERVE+RETRY'
RECIPE_VERIFY = 'REOBSERVE+REVERIFY'

# Frozen set, moved verbatim from decision_policy.RECOVERABLE_PICK_ERRORS
# (originally task_fsm_server.py:308).  decision_policy re-exports this
# object; the identity is unit-tested both ways.
RECOVERABLE_PICK_ERRORS = frozenset({22, 23, 30})


def recovery_eligible(action, error_code, outcome):
    """True when the bounded recovery recipe may plausibly fix this failure.

    Pure function over (action, legacy error_code, outcome).  No budget
    math here: budget spend is accounted by the budget owner (FSMPolicy).
    """
    if action == ACTION_PICK:
        return (int(outcome) != PLUMBING_OUTCOME
                and int(error_code) in RECOVERABLE_PICK_ERRORS)
    if action == ACTION_VERIFY:
        return int(outcome) != 0     # any non-verified outcome (frozen)
    return False
