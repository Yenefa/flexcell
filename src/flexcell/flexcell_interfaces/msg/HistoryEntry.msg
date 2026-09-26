# One bounded history digest entry (WorldState v2 task context): what was
# decided and what came back. Filled by the EXECUTOR from typed skill results
# only (ADR-002 B1) - never from logs, never from policy free text.
uint32 seq
string action                    # ActionKind of the decision
string target                    # object_id / zone_id composite ("" for OBSERVE/WAIT/ABORT)
uint8 OUTCOME_NONE=255
uint8 outcome                    # typed skill outcome; OUTCOME_NONE when not measured
uint16 error_code
uint32 attempt
uint64 world_revision
string evidence_id
