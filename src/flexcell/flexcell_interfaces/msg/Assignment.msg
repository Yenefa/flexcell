# One (object, zone) leg of a task plan (WorldState v2 task context, ADR-002).
string object_id
string zone_id
uint8 OUTCOME_NONE=255
uint8 outcome             # typed skill outcome for completed legs; OUTCOME_NONE otherwise
uint16 error_code         # 0 = none
