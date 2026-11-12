# Post-return feedback and bounded finishing — preregistration

Base: `4746a637`. Existing safe-reposition adapter enabled identically for both
arms; frozen core push contract, TaskSpec, nine files, gripper limit and all
independent acceptance rules remain unchanged. Isolated Gazebo development only.

## Candidate

After each completed PushObject, wait for fresh measured arm velocities at/below
the existing MoveToPose stop threshold (0.02 rad/s) for 0.2 wall seconds, then request
a fresh canonical WorldState. Decide from signed displacement relative to the
declared task start, including return motion. Missing/stale state never becomes
zero progress. Carry/protected-object/envelope violations refuse further motion.

Request at most 30 mm, explicit legal 5 mm overdrive, one increment. This avoids
dividing a short shot into several sub-clearance moves that can trigger contact
loss before the final target. It remains a hypothesis about actual contact, not
an assumed controller improvement. Stop when the known TaskSpec geometry is met;
that state is named GOAL_GEOMETRY_REACHED, not full independent task acceptance.

## Stage A — instrument and contact feasibility

Pure and real-ROS synthetic checks must cover signed returned state, completed
geometry with remaining nominal distance, budget, protected motion, missing motion
state and cancellation. Synthetic messages never count as robot evidence.

One development-instance feedback pilot, seed2000, contact height 0.0200 m, at
most three PushObject requests. Retain all physics/contact/joint/phase data and
grade with the frozen evaluator. Feasibility requires at least 5 mm measured
forward progress, legal request fields, no observed carry/protected movement, and
no post-return state failure. It need not already pass the complete task.
If it cannot establish contact, inspect measured targets/path before choosing
another candidate; do not silently enlarge the shot or repeat until green.

## Stage B — fixed comparison, only after feasible instrument/contact

Preregister three pairs (six fresh worlds), same dev seed2000, same image/world,
same safe repositioning, same three-attempt budget and max 600 s task budget:
old recovery (A) vs feedback (B), in order **A1 B1 B2 A2 A3 B3**.
Pilot data is separate, never pooled into this fixed batch. Every failed run stays.

Primary: full frozen task acceptance, with valid-run and infrastructure counts
separate. Secondary: final signed net motion, per-request contract failures and
overshoot, attempt count, post-return movement, lift/protected/gripper/attachment
evidence. No effect claim from a positive stroke sum; no success-rate or
generalization claim from n=3 per arm. Report raw counts even if equal or worse.

No runtime access to the independent grader. Geometry reaching and independent
full acceptance remain separate; Agent self-report accuracy is not measured.
Stop a run on unknown state/cancel/carry/envelope violation. A repeated acquisition
failure stops the batch for diagnosis; no substitute physical sample is inserted.

Ordinary release regression remains a documented baseline blocker from the previous
turn. This work changes push scheduling only; it does not edit frozen place semantics
or promote the formal baseline. No held-out instance, hardware, paid model or PR.
