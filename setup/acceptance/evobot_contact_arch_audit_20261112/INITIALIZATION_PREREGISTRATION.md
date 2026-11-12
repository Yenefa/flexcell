# New initialization adapter: one infrastructure-only Gazebo check

Before launch, copy the existing velocity-servo world and change only declared
model root initial poses through `scripts/task_world.py`. Use a synthetic public
fixture: A=[0.23,0.015,0.0175,0.2], B=[0.20,-0.17,0.0175,-0.1]. This is not a
held-out instance or a robot task result. No expected_goal/answer fields are used.

After ordinary stack readiness, obtain canonical Observe and independent Gazebo
object xyz/yaw. The existing 1 mm initial-position guard plus a declared 0.01 rad
yaw check must match both objects. Checking those same measured poses against the
old default development coordinates must fail. Verify no PushObject/MoveToPose
task goals were dispatched. Retain world/manifest/native traces and all outcomes.
No live set_pose, reset-to-task teleport, geometry/mass/friction or grader change.
