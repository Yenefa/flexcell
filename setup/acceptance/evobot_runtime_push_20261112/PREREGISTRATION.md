Public instruction Runtime acceptance
=====================================

Goal: close the engineering-driver/Runtime gap. Runtime receives public task
fields only, observes the scene, resolves the requested object and region,
submits RunComposite, consumes typed ContactPush results plus fresh final
observations, and emits its own claim. This is a bounded deterministic rule
policy, not an LLM, learning or L4 Develop claim.

Local sequence declared before execution:
- R0: legacy Runtime on unchanged exposed T08 seed2000.
- R1: finger_tcp Runtime on the same task.
- R2 after implementation freeze: blue-object probe, blue at
  (0.215,0.010,0.0175), protected red at (0.200,-0.180,0.0175),
  region centre (0.115,0.010,0.0175), radius0.060.

R0 was an invalid physical control: the harness omitted the legacy backend's
required20mm contact-height parameter. No actuator motion was dispatched.
R0b corrected this declaration; motion started, but the environment disconnected
before its terminal record could be read. R0b remains UNKNOWN. R1/R2 NOT_RUN.
Do not replace, pool, or count these as candidate successes/failures.

Recovery branch was reconstructed via GitHub after environment loss. It is a
new source revision and requires its own build, tests and actual task evidence.
Additional ownership guards: transport exceptions quarantine the task owner;
aborted/canceled executed motion without stop confirmation remains unknown;
the worker does not inherit its coordinator's name remap or wall clock.

One separate CI sequence, frozen at its triggering commit:
- CI_L0: legacy Runtime, exposed original task.
- CI_C1: finger_tcp Runtime, same task.
- CI_C2 only if CI_C1 has Runtime success AND all9 frozen acceptance gates:
  the same frozen implementation on probe_blue.json.

All3 slots use the SAME newly built pinned-dependency image,2CPU container,
task-scoped graph and40 actuator-goal/600s task budget. CI_L0 retains the native
legacy default overdrive; it is not the former engineering CLI control.
No comparison or pooling with older-image K0/K1/K2/K3 results. R2/CI_C2 are
development-declared validation probes, not sealed held-out evaluation.

Task-scoped graph retains Observe,Carry,TaskFSM,unchanged actuator/physics and
one push backend. TaskFSM and ContactPush coordinators use wall clock; the
contact worker uses simulation clock. This does not solve #237's full graph
scheduling problem. No clock/freshness/watchdog threshold is relaxed.

No old TaskSpec, nine frozen files, push arithmetic, gripper gate, default
launch, threshold or history changes. All failed slots are retained. No retry,
paid model, hardware command, formal baseline promotion, main merge or PR.
A branch-scoped CI workflow attempts independent execution; build/test success
alone is not robot ability. Formal status remains CALIBRATION_UNSUPPORTED
until the existing promotion requirements are independently met.

CI build correction, before any CI physics:
run43274183424 stopped at package discovery because repository-root colcon
discovered historical archived workspaces with duplicate package names. No
robot task ran. The next revision constrains discovery to src/flexcell, adds
Python compilation of the new harness, and accepts the standard Apache-2.0
license text path when preparing the pinned model. No robot controller,
trajectory, Runtime planner, task input, threshold or budget changes.
