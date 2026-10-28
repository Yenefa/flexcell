# D3 attachment admission: NO_GO for default qualification

Decision for the current evidence set: **NO_GO_FOR_DEFAULT_ADMISSION**. Keep
DetachableJoint as an explicitly selected experimental oracle; continue the existing
velocity_servo control. This is a qualification decision, not a finding that the
official Gazebo system cannot work. Issues #56–#59 remain open.

| #57 criterion | Observation | Verdict |
| --- | --- | --- |
| Five attach/detach/reattach cycles, no parent/child contact before attach | Three integrated native cycles passed; separate static-parent probe reports five. No contact measurement; the cohorts cannot be combined | NOT QUALIFIED |
| Ten-second SE(3) stability from the measured pre-attach reference | A/B complete attached traces span 9.22/8.56 s; full traces pass <0.8 µm translation / <3.3 µrad rotation, but the requested ten-second/pre-positioned condition was not run | PARTIAL |
| Free fall within 0.5 s after detach, acceleration −9.8 ±20% | Separate static-parent probe reports −9.8021 m/s²; no saved per-frame fit input or corresponding integrated adapter/arm free-fall trace | PARTIAL, not integrated qualification |
| 500 Hz physics step, no >1 m jumps or NaN contact force | Current world max_step_size is 5 ms (200 simulation steps/s); real_time_update_rate=500 is not a 2 ms step. Contact forces were not collected | NOT MEASURED |
| Legacy Pick/Place parity without relaxed tolerances | Initial joint/legacy A passed; complete teleport/joint legacy matrix is absent. Tolerances were not changed | PARTIAL |
| Independent A/B and retired-session protection | A/B channels, cross-object rejection, retired release/re-engage rejection and expiry passed in the native fixture | PASS for that fixture |

The integrated contact-state attach case and documented non-contact SE(3) pre-positioning case
from #56 are still missing. Full relative-transform enforcement and its false-attached
injection from #58 are also not yet qualified: the current skill still checks measured
rise, with the SE(3) trace checked independently afterward. These gaps prevent default
admission even though the implemented lifecycle and two integration tasks work.

The velocity control remains explicitly named and separate from the archived teleport
cohort. Validate it using the committed five-task CI window, unchanged tolerances,
independent verification, exact deployment identity and preserved negative outcomes.
It is a magnetic simulation oracle, not contact-grasp physics. No automatic fallback
silently changes a selected joint experiment.

Next joint admission work must declare the five missing cases before execution, collect
contact/free-fall observations and satisfy every #57 criterion. It then needs a new
decision record before any default change. Current evidence is in
[the archive](../setup/acceptance/trusted_sim_20261027/README.md).
