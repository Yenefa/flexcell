# T08 WorldState acquisition — one Gazebo probe, 2026-11-12

**Acquisition: CAPTURED. New robot capability: NONE. Task: FAILED.**
The existing T08 capability status remains `CALIBRATION_UNSUPPORTED`; L4 is not acquired.

Base source: `30fa2066e787a7b06d4037261bbd9a6d90ce9078`.
Local image: `sha256:97af41edcf2946ef453525fdae2ae3ab8a0754a113c1393932bfc4007a4e6fa0`.
Built using the repository's unchanged Dockerfile and upstream lock. ROS Jazzy,
Cyclone DDS, domain 181, one owned Gazebo instance. No paid model calls.
This environment differs from the previous session; **do not pool this run with the nine old runs**.

## What changed

Added `scripts/diagnostics/record_world_state.py` and its standalone ROS verification
script. The recorder requests `/observe` with at most one request in flight,
retains the complete unrounded WorldState, distinguishes topic from action-result
copies, records real endpoint QoS and push-phase feedback, and excludes snapshots
with failed EE TF, missing gripper state, unavailable/stale objects or wrong source.
It refuses to overwrite an existing output directory.

No recovery policy, push server, push contract, TaskSpec, gate limit, evaluator,
or baseline pin was changed. All nine frozen files match their session-start bytes.
The inherited evaluate.py vs advertised-pin mismatch remains inherited and unchanged.

## The QoS hypothesis was wrong for this version

Source inspection and the live `PUBLISHERS` record agree: `observe_server` publishes
WorldState as **RELIABLE/VOLATILE**, only while executing `/observe`, without a timer.
The nearby TRANSIENT_LOCAL code configures a **CarryState subscription**.

| Actual check | Result |
| --- | --- |
| Synthetic ROS/DDS, publisher exists, no Observe request | 0 topic messages |
| Synthetic ROS/DDS, active Observe | 47 topic + 47 matching result messages |
| Synthetic ROS/DDS, failed TF/default pose | 40 topic messages, **0 usable** |
| Real Gazebo, passive 5-second window | **0** messages, publisher present |
| Same Gazebo, active Observe, 0.5 s between completed requests | **34 usable topic snapshots**, 34 matching action copies |

VOLATILE readers can receive new TRANSIENT_LOCAL writer samples; the reverse
durability request is incompatible. Blindly requesting TRANSIENT_LOCAL would
therefore introduce an incompatibility here. The compatibility checker reported a
**liveliness system-default WARNING**, retained verbatim, not a durability error.
Messages actually arrived. The old session did not retain installed-source identity,
so this establishes the current source/runtime behavior, not certainty about every
historical installation.

## The position sequence is real and useful, but sampled

`analysis.json` and `trajectory.csv` are independently derived from raw messages by
`analyze_probe.py`. There are **34 distinct source timestamps**, not 68 independent
measurements. Topic and action-return copies are identical. First-to-last reception:
19.785 s; median interval 0.590 s; maximum interval 0.781 s; maximum reported object
age 0.137 s. EE x spans 0.19068–0.29134 m and z spans 0.01971–0.18750 m.

This also corrects the old `/tf` interpretation: raw link transforms are relative to
their parents. A constant link5 translation does not imply a static world-to-EE pose.
WorldState uses tf2 to compose the chain.

## The failure is visible during return and approach

Unchanged original recovery driver, dev seed2000, contact height 0.0200 m,
target 0.0900 m, at most two attempts. Both attempts ran. All eight MoveToPose
calls returned SUCCEEDED. Their **measured** endpoint records and push feedback
identify two retreat motions; their reach errors were **6.296 mm** and **5.158 mm**.

| Motion window | Red x in bracketing snapshots | Reverse displacement |
| --- | --- | --- |
| First retreat | 0.214850 → 0.247365 m | +32.516 mm |
| Second approach | 0.247365 → 0.268993 m | +21.628 mm |
| Second retreat | 0.268899 → 0.279305 m | +10.406 mm |

These are sampled brackets, not exact positions at a boundary. Each bracket's
before/after timing offsets are retained in `analysis.json` (maximum 0.543 s),
and object-source age is retained separately. Multiple samples inside the return
windows show the reverse movement; it is not inferred just from final poses.

**The claim that a FAILED retreat is necessary for backward motion is refuted in
this run.** The first retreat succeeded while the box moved backwards. The second
attempt's reverse displacement is already visible during approach; its subsequent
forward stroke mostly leaves the box stationary. Successful low return/approach
motions do not establish collision-free contact geometry. Exact finger/contact
identity and the relative contribution of reach error remain unresolved: no claim
that all contact hypotheses have been separated.

The actual terminal red x is **0.279444 m** from an initial 0.220000 m: net signed
displacement along the requested −x direction is **−59.444 mm**. Blue movement is
0.0 m. The driver's `achieved=+5.141 mm` is its positive per-attempt accumulation,
**not the final net displacement**. PushObject measures `measured_after` before its
own retreat; the return motion is outside that result's displacement interval.
This is why the post-retreat sequence adds information that push result files lack.

## Acceptance and omissions

| Required reporting item | Result |
| --- | --- |
| Physical object movement | Measured; both servers report contact, with no carry observed in sampled WorldState |
| Target end state | **Failed**: red ends in the wrong direction, outside the target zone |
| Full trajectory/contact evidence bundle | **Not acquired**; sampled WorldState is not the physics/contact bundle |
| Full independent acceptance | **False**; unchanged evaluator reports incomplete evidence and failed terminal geometry |
| Known gripper false rejection | Not adjudicated in this diagnostic; no threshold changed |
| False Success | Frozen verdict reports false; no success claim was made |

**Collection error:** I did not retain the Push node's own `push.jsonl`. The legacy
profile lacks a `push_server` configuration entry, so that node used its container
default log directory, which was not mounted. This omission remains explicit.
The raw MoveToPose log, all phase feedback, both push result files, initial/final
simulator truth and complete WorldState messages **are retained**. No missing
RETREAT_RESULT events have been invented or reconstructed as original records.

For a future reproduction, use a **new output root**, the exact archived runner,
and add this bind mount to the Docker run command before starting it:

```sh
mkdir -p work
t08_probe_root="$(mktemp -d "$PWD/work/t08-followup.XXXXXX")"
mkdir -p "$t08_probe_root/default_skill_logs"
cp setup/acceptance/evobot_worldstate_probe_20261112/run_gazebo_probe.py "$t08_probe_root/"
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock run --rm --init \
  --name t08-worldstate-followup -e ROS_DOMAIN_ID=181 -e GZ_PARTITION=t08-worldstate-followup \
  --mount "type=bind,src=$t08_probe_root/default_skill_logs,dst=/root/.ros/flexcell" \
  --mount "type=bind,src=$PWD/scripts/diagnostics,dst=/diagnostics,readonly" \
  --mount "type=bind,src=$t08_probe_root,dst=/artifacts" \
  flexcell-t08:30fa2066 python3 /artifacts/run_gazebo_probe.py
```

This retains the fallback log without altering motion parameters or old evidence.
WorldState does not expose individual EE/gripper source timestamps, and 1.7 Hz
sampling cannot certify continuous support/contact. These files must not be used
as a substitute evidence bundle or a new task pass.

## Next experiment supported by these data

An isolated safe-return candidate can now be motivated by observed reverse motion
**despite successful retreat**. It should be implemented at the authorized
repositioning interface/scheduling boundary, verify actual clearance and measure
post-retreat object state; the frozen push contract and success rules stay fixed.
One original-vs-candidate development-instance pair should test whether the return
still undoes progress. No claim about efficacy is made before that execution.

The exact executed runner is archived here, including its omission. Raw capture
directories are unchanged; `SHA256SUMS.json` records their archived bytes.
