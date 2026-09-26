# Canonical world snapshot (v1.5 - schema FROZEN for the policy-era comparison).
# source is always SIMULATION_GROUND_TRUTH in this stage; a real-robot backend
# would report a different source and must never be silently mixed with it.
std_msgs/Header header
uint64 revision                       # bumps when tracked objects move past epsilon
string source                         # e.g. SIMULATION_GROUND_TRUTH
flexcell_interfaces/RobotStateSummary robot
flexcell_interfaces/WorldObject[] objects
flexcell_interfaces/CarryState carry
flexcell_interfaces/ZoneState[] zones
string[] notes                        # human-readable diagnostics only
