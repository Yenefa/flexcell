"""Report the false-accept / false-reject count at the end of a pytest run.

WHY A CONFTEST
    The corpus summary is the number the paper quotes, so it has to be visible
    in the ordinary test output - not only when a test fails and not only from a
    separate command that a reviewer has to know about. The hook prints it over
    the same cases the tests run, and by construction it cannot change any test
    result.
"""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import casefile                                          # noqa: E402


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    try:
        results = casefile.run_all()
    except Exception as error:                            # noqa: BLE001
        # Never mask the real test result: report the loader failure and stop.
        terminalreporter.write_line(
            "repair-eval cases: corpus could not be loaded: %s" % (error,))
        return
    write = terminalreporter.write_line
    write("repair-eval cases: " + json.dumps(casefile.summary(results)))
    for item in casefile.mismatches(results):
        write("repair-eval mismatch: %s expected %s %s, got %s %s"
              % (item["case_id"], item["expected_status"],
                 item["expected_codes"], item["actual_status"],
                 item["actual_codes"]))
