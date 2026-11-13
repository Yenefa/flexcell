Public Runtime task acceptance — two bounded tasks completed
============================================================

Actual execution source:22f873bae82ce61270a63397fbecdd3a119a115e.
CI run:https://github.com/Yenefa/flexcell/actions/runs/43274720654.
Default execution backend remains legacy; formal baseline NOT_PROMOTED.

What the system can now do
-------------------------
A public English instruction and live Observe result drive a bounded rule
planner, RunComposite and the registered ContactPush action. Each task below
completed two30mm contact primitives and their measured returns. TaskFSM
consumed correlated fresh typed returned states, committed both stages, then
Runtime checked the public region and protected object before claiming success.
Expected_goal is used by the independent grader, not passed to this planner or
primitive. This is an engineered rule-policy execution path, not LLM planning,
Runtime self-development or L4 acquisition.

| Fixed slot | Actual task | Runtime / frozen9 gates | Net signed -x | Task wall time | Actuator goals |
|---|---|---|---|---|---|
| CI_C1 | Original exposed red-block task, protect blue | PASS /9 of9 |60.9318mm |162.08s |24 of40 |
| CI_C2 | Blue target, changed start/region, protect red | PASS /9 of9 |60.9383mm |171.57s |24 of40 |

Both stayed within600s. All four30mm primitives returned about30.465–30.470mm;
all four live returned states were accepted with26.5–107.1ms receipt age under
the250ms limit. Raw selected-finger monitoring reported contact on the actual
registered patch, no unexpected robot collider and maximum patch distance
0.04222mm. These last numbers are the online monitor's records; the independent
full-task verifier separately replayed trajectory, table support, protected
motion, no lift, legal pusher contact, gripper, attachment and no teleport.

Each task has ONE current Runtime trial. Blue is a development-declared probe,
not a sealed held-out test. Do not pool these with the previous engineering
K-series trials or claim population success rate, broad repeatability,
statistical superiority, regression closure or transfer learning.

Architecture and scope
----------------------
The reusable executor receives object/distance/protected names, no TaskSpec or
goal region. It reuses the pinned actual collision-triangle TCP registration
and dense constrained trajectory engine. ContactPush separates stroke outcome,
physical contact, known motion terminal, completed return, arm readiness and
post-return WorldState. Actual ROS UUID/request correlation, freshness and the
shared task motion budget are checked at Runtime admission. Unknown transport
or unconfirmed executed stops quarantine the owner and block further motion.

The task-scoped graph keeps Observe,Carry,TaskFSM,physics/controllers/MoveIt
and one push backend. Coordinators use wall clock; the worker uses simulation
clock and its own node name. The full default graph's #237 issue is still open.
The same newly built pinned-dependency image was used in all three CI slots.
It is a separate measurement from the previous local-image results.

All failures and limits remain visible
------------------------------------
CI_L0 legacy Runtime failed its fresh postcondition(error63). Its recorder also
rejected2 zero-duration contact intervals among15, so there was NO valid full
physical acceptance for that control. It is excluded from physical success-rate
comparison. No contact event was dropped and no duration or threshold was
changed. See #239, CI_L0/bundle_build.log in the raw ZIP and offline_verification.

Local R0 omitted the legacy contact-height declaration and refused with no
motion: invalid physical control. R0b corrected the configuration and failed
Runtime(error62); its complete frozen acceptance also fails. Its status was
initially UNKNOWN during environment loss and became known only after recovery.
These two earlier-image runs remain separate from the CI window.

The first CI build failed because root colcon discovery scanned archived duplicate
packages. Its full log is retained; no physical task ran. Discovery was then
restricted to current source. The executed revision built both packages and
passed289 relevant checks. The older local broad selection's10 PickServer
fixture failures remain tracked in #238, not hidden as a clean full regression.

Permanent evidence and read-only replay
--------------------------------------
- ci_43274720654_physical.zip: original GitHub artifact bytes,18,526,560 bytes,
  SHA25633fbead803028d16d451c180e5d0a80c18bd28c5825b9e8f4607bd10db13d28c.
  Contains native physics/contact streams, joints, WorldState, live action
  results/receipts, source/image/model/task provenance and original verdicts.
- All306 manifest entries and complete coverage were independently checked.
  Rebuilding evidence from the raw streams and running the unchanged grader
  reproduces both9/9 passes. Four recorded typed returned-state admissions
  also pass their contract on replay. See offline_verification.json.
- local_R0_R0b_raw.zip retains both local failures, logs/preregistrations and
  the pre-loss source. The original worktree was saved locally at8cfb484c;
  this obsolete prototype is not the executed CI candidate.
- archives.json records both ZIP digests. CI job logs, results.json and
  recovered_local_results.json preserve the distinction between successful
  tasks, invalid control evidence and recovered failures.

From the repository root, no ROS/simulator is started:

    python3 setup/acceptance/evobot_runtime_push_20261112/verify_archive.py \
      setup/acceptance/evobot_runtime_push_20261112/ci_43274720654_physical.zip \
      /tmp/t08-runtime-replay-UNIQUE

The output directory must be new. This replay does not repair invalid CI_L0
intervals; it preserves its recorder rejection. Nine frozen files, push
arithmetic, old TaskSpecs, gripper acceptance and shipped default launches
remain unchanged. After environment recovery no owned container or simulator
process remains in the selected environment.

Remaining main-line work: fixed Runtime repetitions, ordinary physical task
regression, broader validated inputs and formal held-out evaluation before
any baseline promotion. Main issue #235 remains active. Auxiliary issues:
#237 full-graph scheduling, #238 old fixtures, #239 contact-interval evidence.
