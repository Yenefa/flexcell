# V12 harness: task-scoped ROS graph under the2-vCPU quota

Keep V11 J1 as FAILED during APPROACH: both native sources paused2.267s, guard
canceled, strict stop confirmed, no stroke contact and arm_ready=false. J2/J3
were NOT_RUN. Do not weaken the2s motion watchdog or call that a bounded push.

The execution environment has cpu.max=200000/100000 (2 CPUs). Process evidence
shows the full stack spending significant CPU in unused pick/place/verify/FSM
servers as all receive simulation updates. V12 changes only the isolated harness
graph, not candidate V11 source, physical world, robot, physics step, controllers,
MoveIt, task, success/freshness rules or installed/default launches.

Generate a pinned trusted_sim copy with only its week1 include redirected to a
copy that removes exactly pick_server/place_server/verify_server/task_fsm_server.
Retain Observe, Carry, PushObject, MoveToPose and all original robot/bridge/
controller/MoveIt startup. Assert the original seven-node set and preserve
original/generated launch hashes. Both new arms use this same graph. Preserve
D1 separately; do not pool it as the new paired control.

Freeze before serial K0/control domain166, then K1/candidate domain167. Same
exposed seed2000/image/world/task/demo_veryslow/60s executor deadlines/two30mm
requests/candidate40-goal cap. K0 uses unchanged prior feedback/high-hold source.
K1 uses exactly V11 candidate motion/geometry/native/receipt/driver sources.

Only if K1 has two bounded strokes, two ready/geometry-valid completed-return
receipts, true registered native contact and frozen full9/9 PASS, execute fixed
K2/domain168 then K3/domain169 confirmations with the same frozen sources/graph.
Keep K1 separate from the confirmation pair; no replacements or tuning. Report
each guard/source failure and unfinished slot. Report native wall gaps and ROS
process count to assess the graph change, without claiming isolated causality
from one comparator or treating the quota as proven universal root cause.

Capability claims, if earned, are limited to this task-scoped isolated graph and
exposed instance. Full default Runtime resource behavior, unseen transfer,
statistical reliability, ordinary release, formal promotion and L4 remain open.
