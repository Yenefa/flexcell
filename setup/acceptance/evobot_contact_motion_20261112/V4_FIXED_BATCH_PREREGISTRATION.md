# V4 fixed batch: coherent native and ROS clocks

This supersedes the unexecuted V3 fixed batch plan before any of its slots ran.
Retain that preregistration and preexecution snapshot. V3 pilot2 had two bounded
stroke SUCCESSES, final60.981mm and full frozen9/9 PASS, but its second return
was canceled by the freshness guard. Strict stop was confirmed; second receipt
correctly retains primitive SUCCEEDED, return_completed=false and arm_ready=false.
It is not a completed-return success and is not pooled into the new batch.

At that cancellation both native streams were560ms old and mutually coherent,
with source stamps10ms AHEAD of the node's ROS /clock. The V3 pause exception
incorrectly accepted only one sign of the bounded transport offset. V4 permits
the absolute clock/native difference to be <=15ms (three physics steps), still
requires native stream difference<=5ms and a2s wall watchdog. Advancing clock
without telemetry or a long wall hang still refuses. Record exact freshness
ages/differences on any future refusal. A pure negative/positive fixture covers
this actual10ms-lag counterexample. Geometry, stroke planning, contact guard,
joint/receipt freshness, return guards and frozen success rules are unchanged.

Freeze V4 and execute exactly these slots serially:

1. B1: V4 candidate, domain215.
2. A1: prior feedback/high-hold control, domain214.
3. B2: same V4 candidate, domain216.
4. B3: same V4 candidate, domain217.

All use the same exposed seed2000/image/world/task/frozen evaluator, two30mm
requests, demo_veryslow,60s executor deadlines and candidate40-goal cap. This is
a combined treatment comparison, not isolation of individual components. Keep
all outcomes and no replacements. Stop for diagnosis if actual physical guard
violations occur; a remaining freshness/return failure is retained in its fixed
slot, not replaced or silently tuned. Do not pool the pilots or prior batches.

Report bounded stroke success separately from returned-request geometry,
known terminal, completed return/arm readiness, full9-gate grading and live ROS
receipt consumption/expiry. Three candidate runs only test repetition on the
current exposed instance. No statistical superiority, unseen generalization,
formal promotion, release consistency or autonomous L4 conclusion is licensed.
