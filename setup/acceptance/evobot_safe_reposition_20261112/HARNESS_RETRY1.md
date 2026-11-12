# Candidate acquisition failure retained; one infrastructure retry

The first candidate session sent **no PushObject goal**. Its observation preflight
failed: joint samples arrived, WorldState had zero samples and its first Observe
goal response was still pending when the outer readiness deadline stopped it.

Checks after cleanup found only the owned container init/idle process; no residual
ROS/Gazebo server, no OOM or OOM kill. Startup/source loading was slower than the
control. The recorder's READY event was about 5.29 s after its own acquisition
start, and its first goal had only about 12.4 s to respond before outer termination,
less than the recorder's declared 15 s per-request timeout. Thus the outer
readiness budget did not let the inner diagnostic finish. The reason for the
unanswered goal itself is **UNKNOWN**, not attributed to QoS or the motion adapter.

Preserve `candidate/` as INVALID_INFRA with zero physical attempts. The exact
original harness is `run_arm.v1.py`; original preexecution hashes remain intact.

Before one retry, change acquisition scheduling only: independent candidate ROS
domain 182, unique partition/output label `candidate_retry1`, outer readiness
budget 60 s. The existing recorder still has its own 15 s request timeout and
will refuse on failure. No motion source, geometry, task, physics, tracking or
acceptance parameter changes. The control is not rerun or replaced.

If observation fails again, retain it and diagnose while the server is available;
do not begin repeated physical trials or report a robot failure from missing data.
