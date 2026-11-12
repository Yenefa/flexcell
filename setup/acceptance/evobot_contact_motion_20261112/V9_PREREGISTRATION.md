# V9: join measured joints to authoritative physical time

V8 G1 retained as FAILED after HOVER/before stroke. G2/G3 are NOT_RUN. Its
contact telemetry guard progressed beyond the earlier rejection, but state()
refused fresh measured joints while node /clock lagged native time by20ms.
Both input freshness and temporal coherence are required; a transported ROS
consumer clock is not the authority for the producer's JointState stamp.

V9 keeps200 measured joint samples in a bounded deque. Select the newest complete
sample at/before the latest exactly paired native physical step, requiring both
source age and wall receive age<=250ms. Retain newer unmatched samples for a
later physical frame. No extrapolation, negative-age acceptance or age clamp.
Log both chosen joint/native source stamps and both ages in events. Required
joint names, finite values, gripper-change, FK cross-check, primitive/return and
frozen task rules remain unchanged. Unit counterexamples cover a newer future
sample, no coherent sample and independently stale wall/source clocks.

Freeze V9. H1/domain231 is the two-request development validation. Only if both
bounded strokes and both ready/geometry-valid returned receipts pass, with true
registered contact and full frozen9/9 grading, run the fixed H2/domain232 then
H3/domain233 confirmations with identical V9 source. Keep H1 separate from that
pair; retain all failures without replacement or tuning. Earlier descriptive
control D1 remains separate. Same exposed seed2000/world/task/image/demo_veryslow,
60s executor deadlines, two30mm requests and40-goal cap. No formal promotion,
unseen/statistical reliability, ordinary release, Runtime or L4 claim.
