"""Repair-eval primitives for the v0.2 paper path (issue #248 / #249).

Imports must stay pure standard library: nothing in this package may import ROS,
pawn a simulator, call a model, or read the network.  The package holds the pieces
that decide *what a condition is allowed to see* during a repair run:

* benchmark.repair_eval.visibility -- the versioned visibility boundary, its policy
  document (visibility_policy.json) and the agent-facing tool gate.

The submodule is imported on demand so that
"python3 -m benchmark.repair_eval.visibility --demo" runs it exactly once.
"""
