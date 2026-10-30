# Local Gazebo execution evidence

See `docs/LOCAL_GAZEBO_RUN_20261031.md` for the actual result and limits.
`local-audit.json` records five baseline cases matching expectations and the
one stopped Joint/MTC task, plus raw-file SHA-256 values.
`receipt.json` identifies the complete 242-member delivery ZIP.
`audit.py` is the actual post-run, read-only auditor; it expects the retained
WSL raw directory. `audit-correction.json` retains the initial auditor's startup
versus task-interval mistake; all raw frames and the earlier auditor remain in
the complete ZIP. No physical window was replaced or repeated.
