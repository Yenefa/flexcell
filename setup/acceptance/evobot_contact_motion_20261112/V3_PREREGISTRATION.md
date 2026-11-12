# V3: distinguish paused simulation from missing native steps

Pilot1 (executed V2) is retained as FAILED/STATE_UNKNOWN, 9 actuator goals,
26.42mm final net movement, no return/next goal. Native source at cancellation
was 389ms old in BOTH streams, with matching simulation stamps. The simulator
had not advanced during that wall scheduling gap. Actual selected-finger contact
was confirmed; no geometry or frozen acceptance change is justified by this run.

Change only candidate native freshness: retain the 250ms normal wall-age limit;
permit a bounded pause up to2 wall seconds only when physics/contact source
stamps differ by at most5ms and both are within15ms of ROS simulation /clock.
Advancing /clock without native frames still refuses. Measured joint freshness,
post-return receipt expiry, strict unknown/cancel handling and all physical
guards stay unchanged. Tests cover paused, advancing-without-data and wall-hang
cases. This is a monitor correction, not a contact-motion success claim.

Next minimum experiment: one V3 candidate pilot, same seed2000, model, geometry,
85degree pitch, 4mm segments, two requests/40 goals, same frozen grader. Preserve
all source versions. The original mechanism gate remains binding. No control or
repeat batch is earned until a bounded stroke, true registered contact and
ready/geometry-valid returned receipt all pass in one attempt.
