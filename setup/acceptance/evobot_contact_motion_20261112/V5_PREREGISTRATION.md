# V5: keep observations alive while planning

V4 fixed batch terminated after its first slot. B1 FAILED after one successful
HOVER actuator goal, before any stroke. A1/B2/B3 are NOT_RUN; the batch is
INCOMPLETE, not a completed comparison. Do not overwrite or reuse those labels.

Evidence: driver /clock remains14.310s through synchronous mesh planning, while
native physics/contact reach29.470/29.830s. `state()` then refuses fresh measured
joints. This is observation/executor starvation during CPU-bound planning, not
an absent-contact result or a reason to weaken source-age limits. The physical
run and full frozen failure remain in the archive.

V5 changes only planning scheduling: pure geometry runs in one background worker;
the sole main ROS thread continues clock/joint/contact callbacks, caller-cancel
and observation guards. The worker owns no ROS client or actuator. A changed
target/gripper, stale source or cancellation refuses dispatch. The existing
handoff still checks the measured start again. No joint/receipt age relaxation,
contact geometry change, success-threshold change or second controller owner.
Tests require planning to make progress only while main-thread observation
callbacks execute, and require changed-observation refusal with zero dispatch.

Freeze V5 before exactly these new serial slots, all exposed seed2000:

1. C1 candidate, domain218.
2. D1 prior feedback/high-hold control, domain219.
3. C2 same V5 candidate, domain220.
4. C3 same V5 candidate, domain221.

Same image/task/initialized world/frozen grader, demo_veryslow,60s executor
deadlines, two30mm requests and candidate40-goal cap. Keep all outcomes without
replacement. No tuning within this batch. An actual physical guard violation
stops for diagnosis; unknown/freshness/return failure stays in its original slot.
Report incomplete batches and all pilots separately. This is a combined
treatment comparison, not a formal baseline or component-isolation experiment.

Success evidence requires bounded stroke verdicts, native registered contact,
completed return with fresh arm_ready and returned-request geometry, continuous
native TCP/pitch tracking, live receipt acceptance/expiry and separate full9/9
grading. Three repeats only concern this current exposed instance; unseen
transfer, statistical superiority, ordinary release consistency, Runtime Agent
integration, formal promotion and L4 remain outside the claim.
