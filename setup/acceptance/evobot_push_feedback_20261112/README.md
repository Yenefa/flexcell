# T08 measured feedback — three repeated development-task passes

The fixed v2 batch completed **candidate 3/3 vs previous recovery 0/3** full
independent task passes. One ordinary pick/place regression also passed. These
are raw counts on **one exposed development instance**, not a general success
rate, an unseen-instance result or a formal baseline promotion.

## Executed change

The isolated controller re-observes canonical WorldState after each completed
PushObject and measured arm settling. It measures **signed net displacement from
the task start**, including return motion. It requests at most 30 mm with legal
5 mm overdrive and one increment, with a maximum of three attempts. It stops when
the known task geometry is reached; it never calls the independent grader online
or labels that geometry decision full acceptance. Missing motion/object state,
carry, protected movement, cancellation and task-envelope violations stop dispatch.

The opt-in return adapter now supports LIFT→TRANSFER and **holding high** instead
of lowering again to a stale retreat point. APPROACH retains LIFT→TRANSFER→LOWER.
The original low retreat target is honestly reported **unreached**, with its
actual error and HIGH_HOLD event. The frozen core receives RETREAT_RESULT=false;
this is not a successful original low-point motion. Actual waypoint failures and
clearance/carry/cancel guards remain enforced.

Both `safe_reposition_enabled` and the new
`safe_reposition_hold_retreat_high` default **false**. The development CLI is
`src/flexcell/flexcell_skills/run_push_feedback.py`; the experiment runner enables
the flags and supplies the previously measured clearance. This is a driver for
the declared single push objective and robot/world, not a general task planner.
No shared installation or ordinary launch was changed.

## Fixed comparison

Preregistered order: **A1 B1 B2 A2 A3 B3**. A is the previous three-waypoint
recovery; B combines measured feedback, bounded requests and high return. Both
have the same three-attempt cap, image, unchanged development TaskSpec, contact
height 20 mm, world, physics and frozen validator. Actual PushObject calls total
five per arm. The comparison does **not isolate** the contribution of any one
component. Task seed2000 fixes the declared scene, not OMPL's realized randomness.

| Run | Final signed forward displacement | Full acceptance | Failed gate | Push calls |
| --- | ---: | --- | --- | ---: |
| A1 | −149.296 mm | FAIL | terminal | 2 |
| A2 | +68.032 mm | FAIL | table_support | 2 |
| A3 | +159.540 mm | FAIL | terminal | 1 |
| B1 | **+61.558 mm** | **PASS, 9/9** | — | 2 |
| B2 | **+50.537 mm** | **PASS, 9/9** | — | 2 |
| B3 | **+76.131 mm** | **PASS, 9/9** | — | 1 |

All six slots executed, with zero infrastructure failures and no replacement,
optional stopping or tuning between slots. All candidate decisions stopped at
GOAL_GEOMETRY_REACHED before an unnecessary additional shot. The independent
verdicts were produced afterward. Batch wall time was approximately 401.5 s;
there were zero model calls, paid calls or hardware actions.

Each passing candidate has valid pusher contacts, table support, protected-object,
gripper, no-lift, no-attachment and no-teleport evidence. Native trajectories have
3,869 / 4,438 / 2,632 steps per object, consecutive 5 ms spacing, without gaps.
Protected excursion is zero to recorded precision. Worst candidate return loss
is 1.678 mm; every completed candidate return stays within the preregistered
5 mm bound. Measured high endpoints are at least 197.747 mm, above the declared
187.791 mm minimum. Endpoint checks do not prove whole-arm swept-path clearance.

Final truth follows a two-wall-second observation window after driver exit.
Candidate final truth differs from its last controller snapshot by −0.339 /
−0.127 / +0.265 mm along the push axis. Retained final 0.5 simulation-second x
ranges are 0.223 / 0.003 / 0.023 mm. A quiet arm alone is not evidence of a settled
object; the report keeps these time windows separate.

## Failures retained; narrow stroke control is still unresolved

The v1 pilot **FAILED**, final net −86.016 mm. Its last online snapshot was
−56.489 mm, followed by further reverse motion; `FINAL_STATE_CORRECTION.md`
preserves that correction to the v2 preregistration's shorthand. Native physics
aligned to waypoint logs localizes about 99 mm of reverse movement to a second
retreat LOWER interval. Endpoint clearance alone did not preserve displacement.

The v2 pilot, which removed that final lowering, also **FAILED the full task**:
final +11.375 mm. Its complete returns stayed within 5 mm loss and it passed the
preregistered mechanism gate, allowing the fixed batch. The second stroke itself
reversed the object; a third approach failed its reach check. The two pilots are
not pooled into the fixed batch, and both raw failures remain available.

**All five candidate PushObject calls in the fixed batch still returned FAILED**
under their narrower stroke contracts, including under-delivery and overshoot.
The 30 mm request cap does not bound physical displacement to 30 mm. A task can
pass its broader unchanged 30–150 mm/zone goal while a stroke misses its requested
distance. This work improves returned-state task completion, not precise stroke
control or general contact repeatability.

No Runtime Agent claim was supplied. The evaluator's default claim flags,
including false_failure on passing probes, are harness artifacts. Agent claim
accuracy and False Success rate are **NOT_MEASURED**, not measured zero.

## Ordinary regression and remaining boundaries

One unchanged normal legacy velocity-servo pick/place smoke with this candidate
overlay passed PICK→PLACE→VERIFY, error 10.766 mm within the existing 60 mm
verification tolerance, zero model calls and zero source/native identity
mismatches. Both reposition flags remained at their default false values.

The previous candidate and original-source normal runs failed gripper release;
those remain in `evobot_safe_reposition_20261112/raw_runs.zip`. This one pass does
not erase them or establish release reliability. Place/pick/carry/common/task-FSM/
MoveToPose sources are unchanged. The new smoke is a PASS; broad non-regression
and the historical release blocker remain unresolved. No frozen release changes
or threshold adjustment was made.

Nine frozen files and `contracts/push.py` match session-start and `30fa2066` bytes.
All executed v2 motion-source hashes match `preexecution_v2.json`. The inherited
stale baseline pin was not refreshed. Formal T08 remains
**CALIBRATION_UNSUPPORTED; baseline NOT_PROMOTED; Runtime-autonomous L4 NOT_ACQUIRED**.
No held-out instance, PR/main merge, release or real hardware was used.

## Evidence and replay

- `PREREGISTRATION.md`, `V2_PREREGISTRATION.md`, preexecution records and exact
  `versions/v1/` and `versions/v2/` snapshots preserve the adaptation boundary.
- `result_summary.json` is the concise machine-readable result;
  `run_analysis.json` includes per-route motion, native waypoint alignment,
  controller decisions, drift and all independent gates.
- `raw_runs.zip` retains all eight T08 runs, the ordinary regression, real-ROS
  synthetic protocol checks, unit output and acquisition logs. Every member is
  verified by `raw_runs_sha256.json`; synthetic fixtures are explicitly not
  physical evidence. There were 95 relevant unit checks and four ROS protocol
  checks; these validate code behavior, not robot ability.
- Image `flexcell-t08:30fa2066`, digest
  `sha256:97af41edcf2946ef453525fdae2ae3ab8a0754a113c1393932bfc4007a4e6fa0`;
  copied T08 world SHA256
  `41aaada28216c028e8552fffc1971cf8b37d84594a16fbccc6de2fead0bc92f9`.
  Each run records actual imported overlay paths/hashes; the image revision tag
  alone does not identify the candidate source.

Read-only replay, after extracting the archive to a fresh directory:

```sh
python3 setup/acceptance/evobot_push_feedback_20261112/summarize_results.py /path/to/extracted
python3 setup/acceptance/evobot_push_feedback_20261112/analyze_runs.py /path/to/extracted pilot1 pilot2 A1 B1 B2 A2 A3 B3
```

Next: validate release consistency and freeze an isolated candidate for unused
instances, with all failures retained. If finer pushing is needed, first separate
wrong contact/approach geometry from stroke-path motion using the retained
continuous pose/contact data; do not enlarge retry budgets or loosen the ruler.
