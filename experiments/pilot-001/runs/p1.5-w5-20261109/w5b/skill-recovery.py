"""Recovery decision used by the workcell executor."""


def next_action(outcome, error_code, budget):
    """Return the next step after a skill result.

    Allowed actions (the executor accepts only these):
      "DONE"    - task finished successfully
      "OBSERVE" - re-observe before retrying a recoverable failure
      "RETRY"   - retry the failed skill
      "ABORT"   - give up (non-recoverable, or budget exhausted)

    outcome: 0 = SUCCEEDED, 1 = FAILED. error_code: 30 = grasp failed.
    budget: remaining recovery attempts.
    """
    if outcome == 0:
        return "DONE"
    return "ABORT"
