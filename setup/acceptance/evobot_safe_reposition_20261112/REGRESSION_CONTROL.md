# One original-source diagnostic after normal-task regression failure

The candidate-overlay normal smoke dispatched one task: PICK passed, PLACE failed
with error 25. Raw place data confirms carry_release_confirmed=true but the gripper
did not open, reached_goal=false, stalled=true, classification GRASP_STALLED.
The audited Python/launch source identity has zero mismatches; place, pick, carry,
common and task executor bytes equal 30fa2066. The opt-in reposition adapter was
disabled for this old-task regression and no PushObject action was requested.

This resembles the previously recorded release failure, but a matching symptom
and unchanged source are not by themselves a proof of causal non-regression.

Before one further run, fix the diagnostic: use the original installed source,
normal case, same velocity_servo/legacy configuration, separate ROS domain 184
and output root legacy_original_control. No motion/configuration/threshold changes.
Keep both outcomes; this is a baseline diagnostic, not a replacement regression.

If the original also fails on the same release operation, report a baseline
release blocker supported by both runs. If it passes, report discordance and
unresolved variability; do not declare the candidate a regression or repeat to
obtain a green candidate. In either case no formal baseline promotion is authorized
by this one comparison, and the frozen release implementation is not modified.
