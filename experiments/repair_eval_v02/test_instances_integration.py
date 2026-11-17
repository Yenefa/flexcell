"""The runner must be able to run a pre-registered instance end to end.

Wiring that has never been exercised is a plan. This drives one slot per instance
through materialize -> boundary -> agent write -> sealed gate -> record, using a
transport that replies with the reference repair. Passing means the pipeline is
sound; it says nothing about whether a real model could find that repair.

The first run of this found a real API mistake: materialize() returned the
editable file path while the caller needed the workspace directory, so every slot
died before the first interaction.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1])):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_a_scripted_agent_can_complete_both_pre_registered_instances():
    import dry_run_instances_scripted as D
    assert D.main() == 0


def test_the_slot_records_the_instance_not_the_synthetic_fixture():
    import instances as I
    assert I.editable_rel("DEF-F1-REG") == "config/week1.yaml"
    assert I.editable_rel("DEF-F2-MAP") == "src/task_fsm_server.py"
    for family in I.FAMILIES:
        assert I.artifact(family)["defect_id"] == family
