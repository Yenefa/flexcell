# T08 WorldState acquisition probe — preregistered before execution

Base: `30fa2066e787a7b06d4037261bbd9a6d90ce9078`. Isolated development only.
No paid model calls. No changes to historical evidence, frozen TaskSpecs,
the nine pinned files, push.py, acceptance thresholds or the execution baseline.

## Evidence already established by source inspection

`observe_server.py` creates WorldState with depth 1 and ROS default
RELIABLE/VOLATILE. Its only publish call is in `/observe` execution. There is
no periodic WorldState publisher. A publisher count is not a message rate.
VOLATILE readers can receive new samples from TRANSIENT_LOCAL writers;
the reverse durability request is incompatible. Do not blindly change the reader
to TRANSIENT_LOCAL. Inspect the live endpoint before attributing a zero count.

Raw `/tf` entries are parent-relative transforms. A constant link5 translation
does not imply a constant world-to-EE pose. WorldState composes TF via tf2;
its lookup-failure notes and gripper availability must be retained.

## Minimum experiment and decisions

1. Verify the acquisition tool with real ROS DDS and an explicitly synthetic
   event-driven Observe server: passive subscription produces no samples;
   requesting Observe produces topic and action-result samples. Reject invalid
   snapshots (failed TF / missing gripper / unavailable object) as usable data.
   This is instrument verification, not robot execution or physical evidence.
2. One fresh Gazebo instance of **dev seed2000**, contact height 0.0200 m,
   original recovery target 0.0900 m, at most two attempts. Run the unchanged
   original recovery driver, with a passive pre-window followed by the acquisition
   tool requesting `/observe` no faster than 2 Hz, one request at a time.
3. Retain complete WorldState messages with source and receive timestamps,
   actual endpoint QoS, world frame, EE quaternion, joint/gripper availability,
   object availability/age, action failures, push phase/RETREAT_RESULT logs,
   both original push result files, and initial/final simulator ground truth.
   Never round recorded pose values or treat a default pose as a measurement.
4. A topic sequence is acquired only when multiple usable, distinct-time
   snapshots exist. Distinguishing contact/repositioning hypotheses additionally
   requires snapshots bracketing approach, retreat and attempt 2. Missing phase
   coverage, stale data or insufficient sampling leaves the mechanism UNKNOWN;
   no claim that one run must separate the hypotheses.

If active Observe restores samples, change acquisition scheduling rather than
publisher durability. If it does not, inspect endpoint compatibility, action
results, ROS domain and installed source identity. Keep the failure and stop
before a batch. Repeated Observe can add CPU/transport load and updates snapshot
revision counters; this run diagnoses mechanism, not comparative efficacy.

If a reproducible simulation cannot be built here, record the exact build error,
complete the independent instrument verification if feasible, and leave physical
capture NOT_RUN. Do not replace it with synthetic motion or claim a robot fix.
