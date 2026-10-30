# PR #75 local continuation — 2026-10-30

The owner confirmed that PR #75 is authoritative and that no additional local
progress or live experiments need to be reconciled. This record supersedes the
older local handoff for this continuation. The source baseline is
`c2583aec1e507386f5733285fe5399003709b4d0`; main is `4e7800058ca87e264ae7fa0bb5297facee7d4b51`.
PR #75 remains open and unmerged.

## VERIFIED: local checkout and build

- Windows: `C:\Users\fuker\Desktop\workspace\project-033-flexcell\code-clone`,
  branch `feat/native-preposition-cycles`.
- WSL Ubuntu-24.04: `/home/ros/agentic_workcell_ws`, branch `dev/pr75-local`.
  Both checkouts were synchronized to the baseline above without force/reset.
- All 131 previously untracked WSL evidence paths were retained; the before and
  after NUL-delimited path lists match. The old Windows
  `setup/learned_policy_validation/reports/pr39_gpu_2161e4e.json` also remains;
  its filesystem timestamp is 2026-10-23 and it is outside this change.
- Source the existing ROS Jazzy environment. `gz` is supplied by ROS vendor
  packages and appears on PATH after sourcing ROS; its absence in an unsourced
  shell did not mean Gazebo was missing.
- Installed the exact MTC core `0.1.8-1noble.20260915.205448` and capabilities
  `0.1.8-1noble.20260915.211634` required by `infra/Dockerfile.sim`.
  Six new apt packages, no upgrades/removals, approximately 10.6 MB installed.
- The first in-place offline build failed because the existing installation
  could not find `trusted_sim.launch.py`; that failure log remains retained.
  Subsequent inspection found that this path is missing, not a dangling symlink.
  The exact old-install/cache mechanism remains UNKNOWN.
  Fresh isolated build/install prefixes then built all four first-party packages:
  `build/pr75` and `install/pr75`. Existing build/install trees were not deleted.
- Combined colcon result: **661 checks, 0 errors, 0 failures, 0 skipped**.
  Ghost-attribute scan: **40 files, 0 problems**.
- Eight relevant archived-evidence verifiers passed, including the five native
  cycles and the verifier that keeps the earlier 112.617 mm PLACE miss rejected.
  These are archive replays, not new physical simulation trials.

## VERIFIED: latest remote failure

[Offline CI 40956690003](https://github.com/Yenefa/flexcell/actions/runs/40956690003)
passed. [Trusted CI 40956689816](https://github.com/Yenefa/flexcell/actions/runs/40956689816)
failed only in `joint-follow-smoke`; `sim-smoke` and `native-five-cycle-smoke`
passed, while camera-data was skipped. PR review threads were empty at inspection.

The failed artifact ID is `12934381703`. The downloaded ZIP matches the PR's
SHA-256 exactly:

`402775c6b03f1780ceb660cb50da6c584c20ebac56a9e275f256e0f0b4c761e5`

Its original PLACE row and stack log record a successful first PICK followed by
`hover (0/1)` / `GOAL_STATE_INVALID`. `mtc_stages=[]` and `released=false`:
no PLACE trajectory was dispatched and no intentional release occurred.
The complete ZIP is preserved locally under
`artifacts/local-pr75-20261030/ci-joint-failed-c2583ae.zip`.
The separate `/workspace/scratch/...` local window mentioned in the PR is not
available on this computer and has not been claimed as recovered.

## VERIFIED: offline point-offset counterexample

A standalone C++ diagnostic calls the installed upstream MoveIt 2.12.4
`IKConstraintSampler`, its actual KDL solver, and this PR's `positionGoal()`
builder. It creates no actuator clients and starts no Gazebo stack.
The robot description comes from the exact locked ROBOTIS revision
`17efe42bd1df178fa44d49c43250fc4304343dbb`.

The fixture combines the original PLACE physical box pose with the rosbag
joint-state sample nearest the inferred PLACE callback start (4.107496 ms
earlier). The resulting link-local point offset is approximately
`[0.02025033246, -0.00002476078, -0.15882943166]` metres. The declared hover
point is `[0.12, -0.15, 0.1675]` metres. Each diagnostic case uses 16 upstream
pose samples, sampler seed 75 and the existing 0.1 mm goal-region radius.

| Diagnostic case | KDL IK solutions | Position constraint satisfied | Point error among IK solutions |
| --- | ---: | ---: | --- |
| Zero offset, current EE position | 16/16 | 16/16 | 0.025–0.098 mm |
| Measured offset, known reachable current box point | 10/16 | 0/16 | 135.244–319.361 mm |
| Measured offset, declared PLACE hover point | 16/16 | 0/16 | 154.249–314.138 mm |

The reference posture itself satisfies the known-reachable point constraint.
Nevertheless, the complete upstream sampler rejects both nonzero-offset cases
within the fixed 16-attempt diagnostic. The zero-offset complete sampler passes.
This is a concrete compatibility counterexample, not a robot success-rate estimate.

The upstream sampler samples a free quaternion and uses that rotation when
undoing the link-local point offset; the configured position-only KDL solve
does not enforce that sampled orientation. The returned link position can be
accurate while the rotated attached point violates the original constraint.
See the fixed upstream
[sampler source](https://github.com/moveit/moveit2/blob/2.12.4/moveit_core/constraint_samplers/src/default_constraint_samplers.cpp)
and [KDL source](https://github.com/moveit/moveit2/blob/2.12.4/moveit_kinematics/kdl_kinematics_plugin/src/kdl_kinematics_plugin.cpp).

**STRONG INFERENCE:** this incompatibility explains the same failing path in
the PR's PLACE hover. **UNKNOWN:** whether it is the unique cause of that
particular full planning failure. The original complete planning-scene snapshot,
planner request and random state were not recorded. The fixture reconstructs
point geometry; it does not reproduce the exact collision scene or MTC task.
Do not upgrade this result to an exact frozen-scene reproduction.

The diagnostic source, all attempts, parameters, fixture provenance, build/test
logs and byte hashes are saved in
`setup/acceptance/pr75_local_20261030/`. `run.sh` is the exact original local
invocation and still references this chat's `work/pr75-ik` source directory.
It deliberately refuses to overwrite an existing fixture directory. The CMake
project can also be rebuilt directly from the archived sources; mesh resolution
requires the retained pinned model-prefix on AMENT_PREFIX_PATH.

## Next development task and acceptance boundary

Implement and validate a solver adapter that solves the actual attached point
while preserving the four-DOF position-only contract and existing scene collision
checks. First require this known-reachable counterexample and the actual hover
point to pass independent FK point validation; keep the zero-offset path and
failure/cancellation/deadline contracts intact. Before a new declared robot
qualification, capture the complete measured planning scene and request so the
next failure can be replayed exactly.

No production solver adapter was changed during this continuation. No new Gazebo
or real-hardware trial was run. The old installed ROBOTIS tree is not the locked
CI revision; only the diagnostic model uses the locked revision so far. A trusted
runtime run still needs the locked upstream build and runtime identity checks.
No PR was merged or pushed. D3 remains **NO_GO**; S2 intervention, moving-parent
detached-reference follow, the legacy matrix and model n>=50 remain unqualified.
