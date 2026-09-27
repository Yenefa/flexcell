#!/usr/bin/env python3
"""Step 0 patch (issue #20): eliminate the PLACE ghost success.

Exact textual deltas on the F: staging tree; every anchor must hit exactly
once or the script fails loudly. Touched files are normalized to LF so the
sync into WSL produces a clean, exact git diff (no CR churn).

Deltas:
  1. place_server.py  - delete the dead `_gate.set_attach` path (undefined
                        attribute since b209225; its crash + rclpy's
                        default-Result fallback manufactured every "success")
                      - add `released` to the jsonl record
                      - crash guard: except Exception -> FAILED + ERR_INTERNAL
  2. all skill servers + task_fsm (both paths) - crash guard
  3. common.py        - crash_detail() helper
  4. 4 skill .action  - uint16 ERR_INTERNAL=2
"""
import sys
from pathlib import Path

ROOT = Path(r'F:\flexcell-stage\agentic_workcell_ws\src\flexcell')

GUARD_PICK_PLACE = """\
        except Exception as exc:  # crash guard (issue #20): a raising execute
            # callback must become a typed FAILURE - rclpy's fallback default
            # Result has outcome=0, which reads as OUTCOME_SUCCEEDED
            return finish(R.OUTCOME_FAILED, R.ERR_INTERNAL, crash_detail(exc))
        finally:
            self._busy = False
"""

PATCHES = {
    # ---------------------------------------------------------------- actions
    'flexcell_interfaces/action/Observe.action': [(
        "uint16 ERR_NONE=0\nuint16 ERR_WORLD_STATE_UNAVAILABLE=3",
        "uint16 ERR_NONE=0\nuint16 ERR_INTERNAL=2\nuint16 ERR_WORLD_STATE_UNAVAILABLE=3",
    )],
    'flexcell_interfaces/action/PickObject.action': [(
        "uint16 ERR_NONE=0\nuint16 ERR_INVALID_GOAL=1",
        "uint16 ERR_NONE=0\nuint16 ERR_INTERNAL=2\nuint16 ERR_INVALID_GOAL=1",
    )],
    'flexcell_interfaces/action/PlaceObject.action': [(
        "uint16 ERR_NONE=0\nuint16 ERR_INVALID_GOAL=1",
        "uint16 ERR_NONE=0\nuint16 ERR_INTERNAL=2\nuint16 ERR_INVALID_GOAL=1",
    )],
    'flexcell_interfaces/action/VerifyObject.action': [(
        "uint16 ERR_NONE=0\nuint16 ERR_OBJECT_UNKNOWN=21",
        "uint16 ERR_NONE=0\nuint16 ERR_INTERNAL=2\nuint16 ERR_OBJECT_UNKNOWN=21",
    )],

    # ---------------------------------------------------------------- common
    'flexcell_skills/flexcell_skills/common.py': [(
        "def pose_msg(position, quat):",
        '''def crash_detail(exc):
    """One-line crash report for the execute-callback crash guard (issue #20).

    rclpy's fallback for a raising execute callback is a default Result whose
    outcome=0 reads as SUCCEEDED/VERIFIED - the Week-1 PLACE ghost success.
    Skill servers convert unhandled exceptions into typed ERR_INTERNAL
    failures carrying this detail instead.
    """
    import traceback
    tail = ' | '.join(
        line.strip() for line in traceback.format_exc().strip().splitlines()[-3:])
    return 'unhandled exception: %s: %s (%s)' % (type(exc).__name__, exc, tail)


def pose_msg(position, quat):''',
    )],

    # ------------------------------------------------------- observe_server
    'flexcell_skills/flexcell_skills/observe_server.py': [
        (
            "from flexcell_skills.common import (\n"
            "    JsonlLog, dist3, new_evidence, pose_msg, sample_gz_pose_age)",
            "from flexcell_skills.common import (\n"
            "    JsonlLog, crash_detail, dist3, new_evidence, pose_msg,\n"
            "    sample_gz_pose_age)",
        ),
        (
            """    def _execute(self, goal_handle):
        t_start = time.monotonic()
        self._seq += 1
        rid, evidence = new_evidence('', self._seq)

        ws = self._snapshot()
        res = R()
        rec = {
            'request_id': rid,
            'evidence_id': evidence,
            'revision': self._revision,
            'available': [o.name for o in ws.objects if o.available],
            'carry_engaged': ws.carry.engaged,
            'zones': {z.id: int(z.occupancy) for z in ws.zones},
        }
        self._pub.publish(ws)
        res.outcome = R.OUTCOME_SUCCEEDED
        res.error_code = R.ERR_NONE
        res.world_state = ws
        res.detail = '; '.join(ws.notes)
        rec.update(outcome='SUCCEEDED', detail=res.detail, evidence_id=evidence)
        self._log.write(rec)
        goal_handle.succeed()
        return res""",
            """    def _execute(self, goal_handle):
        t_start = time.monotonic()
        self._seq += 1
        rid, evidence = new_evidence('', self._seq)
        res = R()
        rec = {'request_id': rid, 'evidence_id': evidence}
        try:
            ws = self._snapshot()
            rec.update(
                revision=self._revision,
                available=[o.name for o in ws.objects if o.available],
                carry_engaged=ws.carry.engaged,
                zones={z.id: int(z.occupancy) for z in ws.zones},
            )
            self._pub.publish(ws)
            res.outcome = R.OUTCOME_SUCCEEDED
            res.error_code = R.ERR_NONE
            res.world_state = ws
            res.detail = '; '.join(ws.notes)
            rec.update(outcome='SUCCEEDED', detail=res.detail)
            self._log.write(rec)
            goal_handle.succeed()
            return res
        except Exception as exc:  # crash guard (issue #20): a raising execute
            # callback must become a typed FAILURE - rclpy's fallback default
            # Result has outcome=0, which reads as OUTCOME_SUCCEEDED
            res.outcome = R.OUTCOME_FAILED
            res.error_code = R.ERR_INTERNAL
            res.detail = crash_detail(exc)
            rec.update(outcome='FAILED', error_code=int(R.ERR_INTERNAL),
                       detail=res.detail,
                       elapsed_ms=int((time.monotonic() - t_start) * 1000))
            self._log.write(rec)
            goal_handle.abort()
            return res""",
        ),
    ],

    # --------------------------------------------------------- pick_server
    'flexcell_skills/flexcell_skills/pick_server.py': [
        (
            "from flexcell_skills.common import (\n"
            "    GripperClient, JsonlLog, MoveToPoseClient, PlanningSceneOps,\n"
            "    dist3, new_evidence, pose_msg, sample_gz_pose)",
            "from flexcell_skills.common import (\n"
            "    GripperClient, JsonlLog, MoveToPoseClient, PlanningSceneOps,\n"
            "    crash_detail, dist3, new_evidence, pose_msg, sample_gz_pose)",
        ),
        (
            "        finally:\n            self._busy = False",
            GUARD_PICK_PLACE,
        ),
    ],

    # -------------------------------------------------------- place_server
    'flexcell_skills/flexcell_skills/place_server.py': [
        (
            "from flexcell_skills.common import (\n"
            "    GripperClient, JsonlLog, MoveToPoseClient, PlanningSceneOps,\n"
            "    dist3, new_evidence, pose_msg, sample_gz_pose)",
            "from flexcell_skills.common import (\n"
            "    GripperClient, JsonlLog, MoveToPoseClient, PlanningSceneOps,\n"
            "    crash_detail, dist3, new_evidence, pose_msg, sample_gz_pose)",
        ),
        (
            """            ok, derr = self._gate.set_attach(False)   # desired: detached
            if not ok:
                return finish(R.OUTCOME_FAILED, R.ERR_PLACE_FAILED,
                              'detach trigger failed: %s' % derr)
            gres, gerr = self._gripper.command(self._gripper_open)""",
            "            gres, gerr = self._gripper.command(self._gripper_open)",
        ),
        (
            """            rec.update(outcome=str(outcome), error_code=int(error),
                       motion_error_code=int(motion_err), detail=detail,
                       elapsed_ms=int((time.monotonic() - t0) * 1000))""",
            """            rec.update(outcome=str(outcome), error_code=int(error),
                       motion_error_code=int(motion_err), detail=detail,
                       released=bool(res.released),
                       elapsed_ms=int((time.monotonic() - t0) * 1000))""",
        ),
        (
            "        finally:\n            self._busy = False",
            GUARD_PICK_PLACE,
        ),
    ],

    # ------------------------------------------------------- verify_server
    'flexcell_skills/flexcell_skills/verify_server.py': [
        (
            "from flexcell_skills.common import JsonlLog, dist3, new_evidence, pose_msg, sample_gz_pose",
            "from flexcell_skills.common import (\n"
            "    JsonlLog, crash_detail, dist3, new_evidence, pose_msg, sample_gz_pose)",
        ),
        (
            """        sampled, err = sample_gz_pose(goal.object_name)
        if sampled is None:
            res.outcome = R.OUTCOME_FAILED
            res.error_code = R.ERR_OBJECT_UNKNOWN
            res.detail = err
            res.evidence_id = evidence
            rec.update(outcome='FAILED', error_code=res.error_code, detail=err)
            self._log.write(rec)
            goal_handle.abort()
            return res

        position, quat = sampled
        exp = goal.expected_pose
        ep = [exp.position.x, exp.position.y, exp.position.z]
        error = dist3(position, ep)
        tol = goal.position_tolerance_m if goal.position_tolerance_m > 0 else self._default_tol
        verified = error <= tol

        res.measured_pose = pose_msg(position, quat)
        res.has_measured_pose = True
        res.position_error_m = error
        res.verified = verified
        res.evidence_id = evidence
        rec.update(measured=position, expected=ep, position_error_m=error,
                   verified=verified)
        if verified:
            res.outcome = R.OUTCOME_VERIFIED
            res.error_code = R.ERR_NONE
            res.detail = 'measured within %.3fm of expected (err=%.4f)' % (tol, error)
            rec['outcome'] = 'VERIFIED'
            goal_handle.succeed()
        else:
            res.outcome = R.OUTCOME_MISMATCH
            res.error_code = R.ERR_NONE
            res.detail = ('measured [%s] outside %.3fm of expected [%s] (err=%.4f)'
                          % (['%.3f' % v for v in position], tol,
                             ['%.3f' % v for v in ep], error))
            rec['outcome'] = 'MISMATCH'
            goal_handle.succeed()  # a mismatch is a valid, honest verification result
        self._log.write(rec)
        return res""",
            """        try:
            sampled, err = sample_gz_pose(goal.object_name)
            if sampled is None:
                res.outcome = R.OUTCOME_FAILED
                res.error_code = R.ERR_OBJECT_UNKNOWN
                res.detail = err
                res.evidence_id = evidence
                rec.update(outcome='FAILED', error_code=res.error_code, detail=err)
                self._log.write(rec)
                goal_handle.abort()
                return res

            position, quat = sampled
            exp = goal.expected_pose
            ep = [exp.position.x, exp.position.y, exp.position.z]
            error = dist3(position, ep)
            tol = goal.position_tolerance_m if goal.position_tolerance_m > 0 else self._default_tol
            verified = error <= tol

            res.measured_pose = pose_msg(position, quat)
            res.has_measured_pose = True
            res.position_error_m = error
            res.verified = verified
            res.evidence_id = evidence
            rec.update(measured=position, expected=ep, position_error_m=error,
                       verified=verified)
            if verified:
                res.outcome = R.OUTCOME_VERIFIED
                res.error_code = R.ERR_NONE
                res.detail = 'measured within %.3fm of expected (err=%.4f)' % (tol, error)
                rec['outcome'] = 'VERIFIED'
                goal_handle.succeed()
            else:
                res.outcome = R.OUTCOME_MISMATCH
                res.error_code = R.ERR_NONE
                res.detail = ('measured [%s] outside %.3fm of expected [%s] (err=%.4f)'
                              % (['%.3f' % v for v in position], tol,
                                 ['%.3f' % v for v in ep], error))
                rec['outcome'] = 'MISMATCH'
                goal_handle.succeed()  # a mismatch is a valid, honest verification result
            self._log.write(rec)
            return res
        except Exception as exc:  # crash guard (issue #20): a raising execute
            # callback must become a typed FAILURE - rclpy's fallback default
            # Result has outcome=0, which for VerifyObject reads as VERIFIED
            res.outcome = R.OUTCOME_FAILED
            res.error_code = R.ERR_INTERNAL
            res.detail = crash_detail(exc)
            res.evidence_id = evidence
            rec.update(outcome='FAILED', error_code=int(R.ERR_INTERNAL),
                       detail=res.detail,
                       elapsed_ms=int((time.monotonic() - t0) * 1000))
            self._log.write(rec)
            goal_handle.abort()
            return res""",
        ),
    ],

    # ----------------------------------------------------- task_fsm_server
    'flexcell_skills/flexcell_skills/task_fsm_server.py': [
        (
            "from flexcell_skills.common import JsonlLog, new_evidence",
            "from flexcell_skills.common import JsonlLog, crash_detail, new_evidence",
        ),
        (
            "        finally:\n            self._busy = False",
            "        except Exception as exc:  # crash guard (issue #20): rclpy's\n"
            "            # fallback for a raising execute callback is a default Result\n"
            "            # with outcome=0 = OUTCOME_SUCCEEDED - never let that happen\n"
            "            return finish(R.OUTCOME_FAILED, R.ERR_SKILL_FAILED,\n"
            "                          crash_detail(exc))\n"
            "        finally:\n            self._busy = False",
        ),
        (
            """        except PolicyStateError as exc:
            self.get_logger().error('policy state error: %s' % exc)
            return finish(RunDemo.Result.OUTCOME_FAILED,
                          RunDemo.Result.ERR_SKILL_FAILED,
                          'policy state error: %s' % exc)
        finally:""",
            """        except PolicyStateError as exc:
            self.get_logger().error('policy state error: %s' % exc)
            return finish(RunDemo.Result.OUTCOME_FAILED,
                          RunDemo.Result.ERR_SKILL_FAILED,
                          'policy state error: %s' % exc)
        except Exception as exc:  # crash guard (issue #20): rclpy's fallback
            # for a raising execute callback is a default Result with
            # outcome=0 = OUTCOME_SUCCEEDED - never let that happen
            return finish(RunDemo.Result.OUTCOME_FAILED,
                          RunDemo.Result.ERR_SKILL_FAILED, crash_detail(exc))
        finally:""",
        ),
    ],
}

expected = {
    'flexcell_interfaces/action/Observe.action', 'flexcell_interfaces/action/PickObject.action',
    'flexcell_interfaces/action/PlaceObject.action', 'flexcell_interfaces/action/VerifyObject.action',
    'flexcell_skills/flexcell_skills/common.py', 'flexcell_skills/flexcell_skills/observe_server.py',
    'flexcell_skills/flexcell_skills/pick_server.py', 'flexcell_skills/flexcell_skills/place_server.py',
    'flexcell_skills/flexcell_skills/verify_server.py', 'flexcell_skills/flexcell_skills/task_fsm_server.py',
}
assert set(PATCHES) == expected, 'patch file set drifted from expectation'

failed = False
for rel, patches in PATCHES.items():
    p = ROOT / rel
    text = p.read_text(encoding='utf-8').replace('\r\n', '\n')
    for old, new in patches:
        n = text.count(old)
        if n != 1:
            print('ANCHOR FAIL (%d hits) %s :: %r' % (n, rel, old[:70]))
            failed = True
            continue
        text = text.replace(old, new)
    if not failed:
        p.write_text(text, encoding='utf-8', newline='\n')
        print('PATCHED', rel)
if failed:
    sys.exit('PATCH ABORTED - anchor mismatch, nothing half-written beyond listed files')
print('ALL PATCHES APPLIED')
