# V10: distinguish read-only planning from actuator admission

V9 H1 remains FAILED after HOVER, before a stroke; H2/H3 are NOT_RUN. Coherent
joint selection worked at startup/dispatch (source age0..15ms) but the planning
loop repeatedly demanded fresh joint frames while CPU-heavy mesh work competed
with ROS on a2-vCPU quota. Its last usable selection aged230ms in simulation;
the strict250ms bound then refused. No source-age threshold change is justified.

V10 changes planning scheduling only. During read-only geometry calculation,
continue cancel/native freshness/target/protected/unexpected-contact guards but
defer joint/gripper-frame admission checks until the completed plan is ready.
Before any actuator handoff, the existing state() gate still requires both
250ms bounds, complete finite joints, unchanged gripper and measured trajectory
start. During actual execution the full joint/gripper guard remains enabled.
The worker owns no actuator; a completed plan cannot bypass stale-state refusal.
A test exercises successful math followed by zero-dispatch fresh-state refusal.
No geometry, trajectory, cancellation, receipt or frozen task rule changes.

Freeze V10. I1/domain160 is the two-request development validation. If and only
if both bounded strokes, both ready/geometry-valid completed-return receipts,
native registered contact and full frozen9/9 grading pass, execute fixed I2/
domain161 then I3/domain162 confirmations with the identical V10. Keep I1 separate
from that pair; keep every failure without replacement/tuning. Earlier D1 remains
a descriptive comparator. Same exposed seed2000/image/world/task/demo_veryslow,
60s executor deadlines/two30mm requests/40-goal cap. No baseline promotion,
unseen/statistical reliability, release/Runtime integration or L4 claim.
