# V6: exact native-step coherence, frozen geometry

Retain V5 C1 as FAILED after HOVER, before any stroke. D1 is the unchanged
control comparator; C2/C3 are NOT_RUN. The V5 batch is incomplete, and its
candidate failure is not erased or replaced. V3 pilot2 remains a full-task pass
with two bounded strokes but only its first completed-return receipt usable.

C1 reveals a sampling bug in candidate telemetry: physics tail at22.855s and
contact tail at22.865s were each within5ms of node /clock22.860s, but the pause
guard compared their unmatched latest stamps and refused the10ms difference.
Reading files in order can naturally produce this two-step lead. No missing
physical contact or geometry error is established by that refusal.

V6 makes freshness use only a contact record and its exactly matching physics
step. Ahead contact records remain pending until their physics row is read;
never label them no-contact. Matching also runs while the monitor is idle.
Reject an unjoinable expired row, physics advancing more than15ms without a
matched contact row, or any existing clock/wall-age failure. Ordinary250ms wall
freshness, bounded2s pause/15ms ROS offset, joint/receipt freshness and every
physical guard stay unchanged. A file-backed fixture covers two-step-ahead
reads, later exact joins and physics advancing without contacts. This changes
telemetry pairing, not robot geometry, motion or task acceptance.

Freeze V6 before three serial candidate repetitions on exposed seed2000:

1. E1 domain222.
2. E2 domain223.
3. E3 domain224.

Use the same world/image/task/profile/demo_veryslow/60s deadlines/two30mm requests
and40-goal cap as D1. D1 was scheduled before V6; it is reported as a descriptive
comparator, not part of a newly randomized or paired superiority trial. Keep
all failures without replacement or tuning. A physical guard violation stops
for diagnosis; any other rejection stays in its original slot.

Report bounded strokes, completed return/fresh readiness, live receipt expiry,
independent native patch/TCP/pitch evidence and frozen9/9 task grade separately.
Three repeats only test this exposed instance. No unseen transfer, reliable
success-rate/statistical-superiority claim, Runtime integration, baseline
promotion, hardware, model spend or L4 claim.
