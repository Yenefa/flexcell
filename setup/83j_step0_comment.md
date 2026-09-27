**Step 0 IMPLEMENTED & VERIFIED** — remote main = `e9137bc` (rebased on PM's da9f0c7 recon docs).

**Ghost eliminated.** Root cause chain: `place_server.py:195` called `self._gate.set_attach(False)` — an attribute defined nowhere since Week-1 `b209225` (DetachableJoint-era leftover). The execute callback crashed on every PLACE; rclpy's fallback for a raising callback returns a **default Result whose outcome=0 reads as OUTCOME_SUCCEEDED**. The box was released before the crash point and free-fell into the zone, so external VERIFY measured honest 2.5-12.8mm while the place skill's own contract (gripper reopen, internal drop check, `released`, evidence record) never executed. Static sweep (setup/82): the only used-but-never-assigned attribute across 14 files.

**Changes (10 files):**

- place_server: dead `_gate` path removed; jsonl records carry `released`
- crash guards on all four skill servers + both task_fsm execute paths: unhandled exception → FAILED + typed `ERR_INTERNAL=2` + jsonl evidence (never the default-Result SUCCESS; VerifyObject's fallback default is even OUTCOME_VERIFIED — same guard)
- `common.crash_detail()`: one-line typed crash report for the guard

**Verified** (`acceptance/week2/m2_2_step0_ghost_fix/`, 83a-83h scripts):

- **place.jsonl: 0 → 9 genuine successes** (released=true, drop-error detail, evidence_id); demo place steps now carry real server detail (`placed target_box_a: drop error 0.006m`) instead of the empty string every pre-fix run showed
- Week-1.5 battery green: happy **byte-clean ×2 vs att3 delivery baseline** (fsm_trace identical, zone 5.7/3.5 + 12.8/9.6mm), recovery (dual-injection → REOBSERVE → retry → success), exhaust (same shape as pre-seam 61_C ERR_SKILL_FAILED + ABORT/BUDGET_EXHAUSTED visible in decisions.jsonl), invalid target (typed IK propagation at PLACE)
- 13 canonical + 15 policy unit tests green; Day-2 regression MOTION_DETECTED=True (off-home arm state — case10's all-joints check structurally fails from the all-zero reset home, pre-existing test-design artifact, documented); clean stop 0 residue
- Environment incidents handled per diary discipline: att1/att2-family servo starvation (load 19-23, measured-not-inherited refused honestly, retry-tolerant re-runs), host sleep killed the stack mid-acceptance (cold restart)

Steps 1-2 (SkillResult v2 status/taxonomy + post-condition verifier) follow on this issue.
