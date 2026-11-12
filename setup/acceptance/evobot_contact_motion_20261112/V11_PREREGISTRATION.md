# V11: unknown input during math does not authorize motion

V10 I1 is retained: one bounded30.494mm stroke SUCCEEDED, but return preparation
stopped because native frames paused2.020s during pure geometry. No return goal
was dispatched; arm_ready=false. I2/I3 were NOT_RUN. The2s motion-input watchdog
must not be raised to make a quiet read-only calculation finish.

V11 completes the planning/admission separation. During pure math, continue
ROS/native callbacks and cancellation; abort on malformed telemetry or a known
scene/contact/protected violation. Temporarily unavailable input does not abort
math, and also does not authorize any actuator. After math, execute() retains
every strict fresh-scene/joint/gripper/measured-start check before registration
or a goal. During physical motion all existing guards stay enabled. Missing
input at that boundary refuses, with no cleanup assumption. No age bound,
watchdog, geometry, trajectory, stroke/return or frozen acceptance change.

Existing unit coverage tests math completion followed by zero-dispatch stale
joint refusal. Add a real-ROS synthetic protocol check: successful read-only math
followed by stale scene telemetry must register/send zero actuator goals. This
is protocol evidence, not physical capability.

Freeze V11. J1/domain163 is the two-request development validation. If and only
if two bounded strokes, two ready/geometry-valid completed-return receipts,
native registered contact and frozen full9/9 grading pass, run fixed J2/domain164
then J3/domain165 confirmations with identical V11. Keep J1 separate from the
pair and retain failures without replacement/tuning. Same exposed seed2000,
image/world/task/demo_veryslow/60s executor deadlines/two30mm requests/40-goal
cap. D1 remains a descriptive earlier comparator. No formal/unseen/statistical
reliability, release/Runtime integration or L4 claim.
