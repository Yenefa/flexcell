# V8: source and consumer clocks have a partial ordering

Keep V7 F1 as FAILED after HOVER, before a stroke. F2/F3 were NOT_RUN because
their prerequisite failed. The frame-pair/prefix replay passed but did not prove
real-time scheduling; do not retroactively relabel this physical failure.

F1's native matched pair was19.030s and node /clock18.985s during a540ms wall
pause. The absolute15ms clock offset incorrectly rejected a45ms ROS transport
lag. Native ECM is the producer's physical time; ROS /clock is its transported
consumer time. Source-leading-consumer does not imply that native steps are
missing. Increasing an arbitrary symmetric offset would hide that distinction.

V8 changes only the pause predicate: within the existing2s wall watchdog and
exact coherent native pairing, reject if ROS /clock is more than15ms AHEAD of
the paired native source. A lagging consumer /clock is permitted. Advancing
physics without matched contacts still refuses. Normal250ms source wall age,
strict joint-state freshness, receipt clocks/expiry, target/gripper guards and
all geometry, motion, cancellation, unknown and task acceptance conditions stay
unchanged. The45ms counterexample is added to the positive/negative unit case.

Freeze V8. G1/domain228 is one two-request physical validation. Only if both
bounded strokes and both ready/geometry-valid returned receipts pass, with true
registered contact and full frozen9/9 grading, execute fixed confirmations G2/
domain229 and G3/domain230 with identical V8 source. Keep G1 separate from the
confirmation pair and retain all failures without replacement or tuning.

Same exposed seed2000/world/task/image/demo_veryslow/60s executor deadlines and
40-goal cap as earlier. D1 is only a descriptive earlier control. No unseen,
statistical reliability/superiority, formal promotion, ordinary release, Runtime
integration or autonomous L4 conclusion. All prior incomplete batches/pilots
remain in the final report.
