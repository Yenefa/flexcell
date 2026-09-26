# Executor-owned hard limits a policy must respect (WorldState v2 task context).
# The executor ENFORCES these (ADR-002 invariants B2/B3); a policy may only
# consume them and may never raise or reinterpret them.
string[] allowed_actions         # ActionKind menu, executor-owned
uint32 recovery_budget           # hard cap on retries per leg; accounting is executor-side
float64 verify_tolerance_m
string motion_profile_id         # whitelist key; raw velocity/acceleration scaling is forbidden
float64 max_world_age_s          # freshness gate input (executor forces fresh OBSERVE when exceeded)
