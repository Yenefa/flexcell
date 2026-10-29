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

## Retained new window

Implementation/declaration commit `8df23906b6868fd7f488733491966697d102a987`
was committed before this one local task. Runtime source/install identities
matched all 181 relevant tracked files. The running MTC executable SHA256
matched the installed build (`bc0809e2566d7cc11456d500e6918fa5e36ef7341f3f1eee7ca979619b7f3f98`),
and the loaded observer/physics engine mappings were captured in the same round.

The first PICK, PLACE and VERIFY all succeeded, with no recovery. The contact
gate joined 9,321 raw 2 ms frames; passive B measured 500/500 prebinding force
samples with mean 0.4899999999957504 N. Ground observations remained UNKNOWN.
All 21 fixed 40 ms release samples were detached/contact-free, acceleration
-9.799999999999867 m/s² and maximum quadratic residual 6.94e-17 m. Final strict
health passed all 19 checks, IDLE and carry released. No camera or model data
collection was requested for this bounded window. Complete original files are
archived in `setup/acceptance/mtc_first_attempt_20261030/`, independently replayed
in offline/native CI. This one success is not a success-rate estimate and does
not identify the historical invalid stage. D3 remains NO_GO; five-cycle and S2
qualification were not run.
