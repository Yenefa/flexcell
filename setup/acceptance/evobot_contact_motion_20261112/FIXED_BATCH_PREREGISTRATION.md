# Fixed exposed-instance mechanism comparison

V3 pilot2's first request met the original mechanism gate: frozen primitive
judge SUCCEEDED for30.478mm, native selected-patch contact, post-return30.490mm,
arm_ready/returned_request_geometry_satisfied true. A separate read-only ROS
consumer received the live receipt, accepted it initially and refused it300ms
later. Keep both pilots separate from the following batch. Pilot2's second
request/full-task outcome will be retained regardless of result.

Freeze the five candidate motion/geometry/receipt/native/driver sources at V3.
No parameter changes or reruns in the fixed batch. Harness additions only record
the actual receipt topic read-only. Existing control source remains unchanged.

Predetermined serial slots on the exposed seed2000:

1. A1: prior feedback + high-hold control, domain214.
2. B1: registered-finger constrained candidate, domain215.
3. B2: same candidate, domain216.
4. B3: same candidate, domain217.

Both arms use the same image, declared initialized world, task, demo_veryslow,
60s MoveToPose executor deadlines, two30mm request limit and frozen evaluator.
Candidate has at most40 actuator goals. The time/actuator/path algorithms differ
as part of the combined treatment. The control is not the formal baseline and
this is not a component-isolation experiment. Do not pool earlier demo_slow
experiments, earlier three-attempt batches or either pilot into these slots.

Report all slots, per-request bounded verdicts, actual returned net displacement,
native patch/trajectory evidence, motion terminal/readiness, live receipt expiry
and all nine full-task gates separately. No replacements or favorable-run
selection. An incomplete slot counts as incomplete/failure, with its logs. A
physical collision/safety guard rejection stops the batch for diagnosis rather
than silently changing the frozen candidate. This minimum batch can establish
repeat execution on this one instance; it cannot establish a reliable success
rate, statistical superiority, unseen transfer, gripper release consistency,
formal baseline eligibility or L4.
