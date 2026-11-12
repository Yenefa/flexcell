Runtime capability checkpoint — incomplete physical acceptance
==============================================================

This branch adds an opt-in public instruction execution path:
Observe -> public rule planner -> RunComposite -> ContactPush -> measured
finger-TCP motion -> typed post-return state -> independent task grading.

Default backend remains legacy. New action and source are an isolated
development candidate; formal baseline is NOT_PROMOTED. Earlier finger-contact
evidence remains at commit8c3972da and must not be attributed to this integration.

The hardest interfaces
---------------------
- The reusable executor takes an object, primitive distance and protected
  objects. It has no TaskSpec, destination or expected_goal input. It reuses the
  pinned actual-triangle finger registration and constrained trajectory engine.
- ContactPush separates stroke outcome, physical contact, terminal knowledge,
  completed return and arm readiness. The returned WorldState and monotonic
  observation time are typed. Readiness service means execution-owner
  availability; it is not a physical arm-ready lease.
- TaskFSM correlates the actual child action UUID and request ID, checks source,
  frame, complete objects, released carry, gripper knowledge and freshness,
  charges a shared task motion budget, and re-observes before committing stages.
- Unknown actuator acceptance/terminal or transport failures quarantine the
  owner and prohibit later cleanup/dispatch. Receipt-only stroke success cannot
  complete a stage when return failed.

Observed before environment loss
--------------------------------
The initial local version built its interfaces and skills;117 focused checks
passed. A broader selection reported309 passes/10 failures in old PickServer
fixtures missing _admission_wait_s. Those source/test files were unchanged;
independent baseline reproduction is assigned in #238. This is not a clean
full-regression claim.

R0 refused for a missing legacy contact-height declaration; its zero-motion
failure is retained and excluded as a valid physical control. R0b started real
motion after that configuration correction. The environment then became
unavailable/offline. Its final result, evidence integrity and process cleanup
are UNKNOWN. New candidate R1 and blue probe R2 had not run.

The raw local directory and uncommitted worktree could no longer be accessed.
This checkpoint was RECONSTRUCTED from the pinned parent and tool-visible
source. It is not asserted byte-identical to the version that passed117 tests.
Original raw logs are not fabricated or replaced with these observations.
See recovery_observations.json for this explicit boundary.

Current verification
--------------------
The branch-scoped t08-runtime-recovery workflow attempts a new interface build,
relevant tests, then exactly one declared three-slot physical window. Only the
workflow's actual logs/artifacts may establish results for this reconstructed
revision. CI_C2 runs only after original-task Runtime AND full9/9 acceptance.
At checkpoint creation this execution is NOT_RUN/PENDING, not a success.

The CI image rebuild keeps Dockerfile.sim and upstream lock unchanged and
records its own identity. Every physical slot uses that same image, unchanged
frozen grading, raw native physics/contact streams, joints, WorldState and
actual Runtime claims. OriginalTask/frozen-nine/push arithmetic are untouched.
The blue probe is an explicit new development validation, not formal held-out.

Resumption
----------
When the original environment returns, first preserve R0/R0b and the old
worktree, inspect only owned container evobot-runtime-push-20261112 and its
process groups, and establish terminal/cleanup state. Do not overwrite old
directories or replay an unknown accepted goal. Compare recovered source with
that worktree and re-run appropriate checks before any further physical slot.

Related: #235 main line; #237 simulation scheduling/environment interruption;
#238 old test fixture repair. Actual task completion is the acceptance standard.
