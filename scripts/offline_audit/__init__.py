"""Read-only offline execution-evidence audit entry (issue #246).

This package only ORGANISES the results of the three existing tools. It does not
re-implement their calculations, does not score the robot task and never writes
into the run directory it reads.
"""

from .cli import audit_archive, build_report, main

__all__ = ["audit_archive", "build_report", "main"]
