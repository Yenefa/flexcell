# Task context inside the canonical WorldState v2. Executor-owned truth,
# assembled at decide() time per ADR-002; observe_server publishes this field
# default-empty and the executor overwrites it in the policy-facing envelope.
string task_state                         # mirrors /flexcell/task_state (IDLE/BUSY/...)
string goal_id
string scenario_id
flexcell_interfaces/Assignment[] plan_remaining
flexcell_interfaces/Assignment[] plan_completed
uint32[] retry_counts                     # per remaining plan leg, same order
uint32 recovery_budget_remaining
string last_action                        # ActionKind of the previous decision ("" = none)
uint8 OUTCOME_NONE=255
uint8 last_outcome                        # typed outcome of the previous action
uint16 last_error_code
uint64 last_action_world_revision
string[] available_actions                # == TaskConstraints.allowed_actions
float64 deadline_remaining_s
bool fault_injection_active               # policies see THAT injection exists, never the schedule
flexcell_interfaces/TaskConstraints constraints
flexcell_interfaces/HistoryEntry[] history
