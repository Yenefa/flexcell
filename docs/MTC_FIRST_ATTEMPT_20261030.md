# MTC first-attempt qualification after the #73 main failure

Main `69ba3d7924cb84784a177ab0efb66eb2d03f6662` passed offline CI and
the five-task MTC regression, but its joint qualification job in run
40919257769 was rejected. One task dispatched two PICK attempts: the first
failed during MTC planning (`GOAL_STATE_INVALID`, no execution); production
FSM recovery succeeded on the second attempt. The strict single-attempt gate
correctly returned STOPPED. The original artifact is preserved byte-for-byte
in `setup/acceptance/mtc_main_failure_20261030/` with an independent verifier.
It remains rejected. The old log does not identify the failing MTC stage, so
that historical stage and exact invalidity mechanism remain UNKNOWN.

The planner previously committed each Cartesian target to a single IK joint
solution before MTC propagated the stage scenes. The IK call had no scene
validity callback. A kinematic solution need not be collision-valid; handing
one frozen solution to OMPL can produce an invalid goal. This is a structural
weakness, not proof of which collision or bound caused the retained failure.

The arm stages now use MTC MoveTo point goals and a thin PipelinePlanner
adapter using MoveIt's official point-only goal-constraint constructor.
The stock MTC PointStamped implementation retains current orientation by
constructing a pose constraint; that would impose an unintended six-DOF
requirement. The adapter creates only a positional constraint, including the
link-local point offset, and delegates planning to the upstream pipeline.
It retains collision checking, propagated stage scenes, path constraints,
deadlines and velocity limits. No custom IK retry loop, disabled collision
pair or tolerance relaxation is introduced. Orientation remains explicitly
unenforced for the four-DOF arm, as in the existing contract.

Failed MTC plans now return a bounded stage-state/failure explanation and
retain its complete text in the stack log. Action APIs and error codes are
unchanged. Native regression tests check that varying target orientation
cannot reintroduce an orientation or fixed-joint constraint and that the
position radius and local offset are preserved.

`infra/joint-contact-position-goal.json` declares one new first-attempt
integration window, after committing this code and manifest. It uses the
same world, 2 ms step, 11 sim s hold, 50 mm qualification release clearance,
2 mm / 1 degree follow limits and 40 ms contact-free release interval as the
previous camera-free contact window. The only configuration change is the
explicit qualification-only recovery budget 0. Production recovery stays 1;
historical manifests/configurations remain unchanged. No replacement task
or extension to the sample count is allowed. Five-cycle and S2 qualification
are deferred until this baseline is resolved. D3 stays NO_GO.

For CI, SOURCE_REV now enters the Docker image after colcon build. Revision
metadata remains fresh runtime provenance; identical source trees can reuse
the tested build after a merge. Source/install/import checks still run before
dispatch. A new source tree still invalidates COPY/build cache normally.
