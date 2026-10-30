# Local attached-point IK evidence

The actual Gazebo windows ran at e30bd8b; aae8487 adds only a test dependency.
`dependency-receipt.json` confirms the planner binary is byte-identical.
See `docs/JOINT_POINT_IK_20261031.md` for the measured results and limits.

`local-audit.json` records all five baseline expectations, one successful Joint
task, independent physical/contact checks and hashes of stable raw files.
`planner-fk-audit.json` replays the exact actual CDR trajectory endpoints with
the original robot model. `receipt.json` identifies the complete 358-member
ZIP, including retained failed numerical experiments and initial audit manifest.
The raw source directory is retained in WSL. Scripts here are the actual local
tools; do not rerun a frozen physical window as a replacement for old results.

Full suite: 662 tests, zero errors/failures/skips. Post-review MTC dependency
check: three CTest entries, zero errors/failures/skips. Static scan: 40 files,
zero problems. Read-only code review found one missing test dependency, fixed;
no remaining actionable findings. D3 admission remains NO_GO.
