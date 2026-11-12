# Existing task regression, after the fixed batch

Run one ordinary legacy velocity-servo pick/place smoke with the candidate Python
overlay, FSM (zero model calls), normal case, default parameters, a separate ROS
domain and output. Use the existing `scripts/sim_smoke.py` and source/native
identity audit unchanged. Both reposition flags default false in this ordinary
launch. Do not run concurrently with the T08 batch or alter release semantics.

Retain the actual task and skill outcomes, including a failure. The previous
candidate and original-source normal runs both failed at the existing gripper
release stall. Reproducing that failure is still a failed regression gate;
source identity does not justify relabeling it as a pass. No second favorable
replacement task or formal promotion is authorized by this check.
