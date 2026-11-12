# Architecture/contact audit: before querying the retained continuous records

Base d87f1701, isolated branch. No modification of nine frozen files, PushObject
core, TaskSpecs, acceptance thresholds, or old evidence. No paid model or hardware.

Audit all five B1/B2/B3 primitive attempts, plus the second pilot2 attempt that
reversed the object. No successful subset selection. Use the existing native
5 ms physics/contact traces, actual MoveToPose execution intervals, and actual
link5 pose composed with the pinned 126 mm fixed EE transform. Raw /tf parent
translations are not world poses. Retain source hashes and native time alignment.

Separate these hypotheses without claiming causality from correlation:

- H1: the actual EE itself moves against the requested direction during a stroke.
- H2: the EE moves forward, while contact is on the top/wrong side and orientation
  changes; endpoint-only point planning does not constrain the contacting tool.
- H3: a substantial part of excess displacement continues after the last observed
  pusher contact, consistent with an impulsive/inertial contribution.

Also test whether the primitive's contact_made=false really means absent native
contact, rather than its displacement-floor definition. Distinguish measured
physical contact, requested stroke, post-return task geometry and full grading.

Minimum new robot experiment, only if retained data supports an impulse/contact
issue: one default-speed / very-slow-profile pair, same exposed dev instance,
geometry, maximum three attempts and unchanged evaluator. The only treatment is
the existing whitelisted profile (0.2 vs 0.05 velocity/acceleration scaling).
This tests whether a configuration-only reduction in impact is a promising
remedy. Both outcomes stay; no favorable rerun or baseline promotion. A pair
cannot identify a general speed effect amid planner/contact randomness. If the
slow profile fails, report rejection and preserve the need for contact/path control.
