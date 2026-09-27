**M2.2 Failure Contract v2** (chief verdict 2026-09-27: fix the foundation before extending — P0 first)

**Problem this closes.** Since Week-1 (`b209225`), every "successful" PLACE was a ghost: `place_server._gate.set_attach` (undefined attribute, DetachableJoint-era leftover) crashed the execute callback, and rclpy's fallback for a raising callback returns a **default Result whose outcome=0 reads as OUTCOME_SUCCEEDED**. The box was already released before the crash point, free-fell ~12mm into the zone, and the external VERIFY measured a real 2.5-12.8mm — end-to-end result real, skill contract fake: gripper reopen, internal drop check, retreat, `released` flag, and the place.jsonl evidence record never executed. `place.jsonl` has **0 genuine success records in its entire history**. Any FSM/Jev/LLM benchmark on this data scores noise.

**Scope (Steps 0-2 of the ratified order):**

- **Step 0 — ghost fix**: remove the dead `_gate` path; crash guard on ALL skill servers and both task_fsm execute paths (unhandled exception → FAILED + typed `ERR_INTERNAL=2` + jsonl evidence; never rclpy's default-Result SUCCESS). VerifyObject's fallback default is even `OUTCOME_VERIFIED` — same guard.
- **Step 1 — SkillResult v2**: `uint8 status` (STATUS_NONE/SUCCESS/FAILURE/SKIPPED) on all four skill results; unified error taxonomy (observe 3→22, +`ERR_VERIFY_FAILED`, taxonomy-only `ERR_TIMEOUT/ERR_STALE_WORLD/ERR_SAFETY_REJECTED`); Observe result +`evidence_id`; executor plumbing timeouts typed; skill error codes enter the decision log. `detail` stays the single human-readable channel — no `error_detail`/`message`/`reason` duplicates.
- **Step 2 — post-condition verifier**: skill-declared SUCCESS ≠ success. Executor checks pick SUCCESS ⇒ `grasp_attached`, place SUCCESS ⇒ `released` (+ pose within zone); violations demoted to typed `SKILL_CONTRACT_VIOLATION` into the failure chain. Planted-violation unit test.

**Non-goals**: no BehaviorTree / Open-RMF / distributed recovery; STALE_WORLD/SAFETY_REJECTED fire later with the safety gate (#6); task-level RunDemo/RunPickPlace contracts unchanged; carry/Gazebo/skill contracts frozen.

**AC**: (a) first genuine place.jsonl SUCCESS record (released=true, drop error, evidence_id); (b) Week-1.5 battery green; (c) happy fsm_trace byte-identical to `delivery_20260926` baseline; (d) unit tests green incl. planted violation; (e) static no-undefined-attr scan clean.
