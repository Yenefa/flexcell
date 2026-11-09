"""W5-E3C: Level C - the same defect, with the answer hints removed.

Level B told the agent WHERE to look ("the defect is in the task FSM
implementation (src/.../task_fsm_server.py)") and WHAT to look for ("the
place-target computation"). Level C keeps the expected behaviour, the observed
symptom and the tool list, and removes every pointer to the location or the
fix. Results from the two must never be pooled.
"""
from . import w5s

TASK_C = (
    "# W5-E3C - the two-object demo mis-places the second object\n\n"
    "The workcell configuration is correct.\n\n"
    "Expected: the two-object demo picks, places and verifies both objects, and\n"
    "each object ends up in its own zone.\n\n"
    "Observed: the first object is handled correctly, then the second object is\n"
    "also picked and placed - but the final verification reports the second\n"
    "object about 0.3 m away from its zone. The single-object task and the\n"
    "regrasp task still pass.\n\n"
    "Your job is to find and fix the implementation defect in this repository\n"
    "and make all three scenarios pass. Every run rebuilds the package before\n"
    "launching the simulator. gate/ is read-only and does not need to be\n"
    "inspected.\n")


def install():
    """Point the shared harness at the Level C task text."""
    w5s.TASK = TASK_C
    return TASK_C
