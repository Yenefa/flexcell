# Legacy/joint release geometry investigation

**Goal:** Identify where a real legacy/joint placement error appears, with one frozen local diagnostic and an independently replayable vector decomposition.

**Design:** Keep the production skill, motion, carry and admission logic byte-identical to PR #85. Use the existing one-task harness, 2 ms physics/contact traces, motion JSONL and raw rosbag. Preserve the original 12 mm release clearance and 60 mm tolerance. Disable recovery for this declared diagnostic. The extra instrumentation and no-recovery setting distinguish this window from the original #86 matrix; do not replace its measurements or claim a rate.

**Alternatives:** Repeating the five-task matrix would measure another maximum without isolating its cause. Changing the legacy target formula before collecting the release transform would conflate diagnosis with a candidate fix. One frozen diagnostic provides the required boundaries at lower runtime cost.

**Hypothesis:** Legacy PLACE targets the EE at box target plus a fixed world-vertical 160 mm, whereas a fixed joint carries a measured link-relative transform. Wrist rotation can therefore create box-target error even when the EE reaches its goal. This is a hypothesis until independently checked against the actual released session. Post-release motion and tracking error may contribute separately.

**Architecture:** Analyze source-bound raw records after shutdown. Select the task's single attached session rather than joining startup/reset segments. Use same-step physics transforms, the bag's EE TF and the actual descend motion target to compare predicted and observed box positions. Retain missing or ambiguous data as UNKNOWN and reject incomplete or tampered evidence. Do not use this diagnostic as a physical qualification.

**Tech stack:** ROS 2 Jazzy, Gazebo Harmonic, existing pinned install, Python stdlib offline math, existing ROS bag deserialization only when extracting TF.

- [x] Read current handoffs, remote #86, skill/motion code and raw-evidence rules; preflight confirms no running simulation and preserves old WSL patch.
- [ ] Commit this plan and `infra/legacy-release-diagnostic.json`; export exact Git LF runtime sources to a new WSL stage.
- [ ] Verify every imported first-party Python/launch byte against the frozen source and reuse native binaries only with their recorded SHA. Materialize and hash the diagnostic world/config before dispatch.
- [ ] Run the declared A task once with the owned harness. Save nonzero exit, raw steps/contact/bag, source revision and all health/reset receipts. No replacement task.
- [ ] Extract exact task-session and release boundaries. Calculate EE target/tracking error, measured rigid offset, box error before release, and post-release displacement separately.
- [ ] Add meaningful positive/negative offline tests for the decomposition and incomplete/ambiguous sources; execute them and independently replay the complete raw window.
- [ ] Review conclusions against the raw records. Fix production behavior only if a separate supported, bounded design is available; otherwise keep mechanism limitations explicit.
- [ ] Publish evidence/conclusions as a new stacked PR, leave bounded low-difficulty followups in existing issues, update handoffs and local delivery. Do not merge, change billing, thresholds, default backend or D3 NO_GO.
