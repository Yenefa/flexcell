# Canonical world snapshot (v2 - additive evolution of the v1.5 freeze, ratified
# 2026-09-26; existing fields are unchanged for current consumers). source is
# always SIMULATION_GROUND_TRUTH in this stage; a real-robot backend would report
# a different source and must never be silently mixed with it.
# Policy-facing bytes are produced by flexcell_skills.canonical_state with
# WorldStateSchemaVersion=2; notes[] never enters that serialization.
std_msgs/Header header
uint64 revision                       # bumps when tracked objects move past epsilon
string source                         # e.g. SIMULATION_GROUND_TRUTH
string schema_version                 # "2.0"
flexcell_interfaces/RobotStateSummary robot
flexcell_interfaces/WorldObject[] objects
flexcell_interfaces/CarryState carry
flexcell_interfaces/ZoneState[] zones
flexcell_interfaces/TaskContext task  # executor-owned at decide() time (ADR-002);
                                      # observe publishes it default-empty
string[] notes                        # human-readable diagnostics only; NEVER
                                      # serialized to policies
