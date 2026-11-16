"""The two wordings of the task, and what each of them gives away.

v1 is what the first matrix used. It names the objects to register (F1) and the
expected pairing (F2), so the no-feedback condition can repair without any
feedback - which is why all four conditions passed F1 and why F2 differed only in
search cost.

v2 states the symptom and nothing else. The names then have to arrive through the
channel a condition is allowed to read: execution feedback for B, C and D, and not
at all for A. That is the contrast the protocol exists to measure.

Keeping both here rather than editing v1 in place means the first batch stays
attributable to the wording it actually ran against.
"""

TASK_TEXT_V2 = {
    "DEF-F1-REG": (
        "The robot cannot see the boxes it is asked to move. The perception service "
        "starts, but it reports nothing the task layer can use, so every task fails "
        "before the first pick.\n\n"
        "The repair surface is the workcell configuration: config/week1.yaml. Nothing "
        "in this task tells you which objects the workcell has."
    ),
    "DEF-F2-MAP": (
        "The robot picks a box and puts it down in the wrong zone.\n\n"
        "The repair surface is source: src/task_fsm_server.py. Nothing in this task "
        "tells you which zone each object belongs in."
    ),
}

VARIANTS = ("v1", "v2")
