# H3 explained: two different send failures, and the staging one is a start-up race

`move_to_pose_server.py:838-857`, the `controller_action` backend:

```python
if not self._fjt_client.wait_for_server(timeout_sec=2.0):
    return ('unavailable', None, None,
            'controller action %s unavailable' % self._fjt_action)
g = FollowJointTrajectory.Goal()
g.trajectory = traj.joint_trajectory
sf = self._fjt_client.send_goal_async(g)
...
gh = sf.result()
if gh is None or not gh.accepted:
    return ('rejected', None, None, 'controller rejected the trajectory')
```

`ERR_CONTROLLER_REJECTED = 20` (`MoveToPose.action:55`).

## The two statuses mean different things

| status | condition | error_code observed |
| --- | --- | --- |
| **`unavailable`** | `wait_for_server(2.0 s)` failed - the controller action server was not there | 31 |
| **`rejected`** | the server was there and **refused the goal** | 20 |

## The staging move's constant failure is a start-up race

The staging move is issued **immediately after the stack comes up**. It reports `unavailable`,
meaning the FollowJointTrajectory action server had not answered within 2 seconds.

**That is why `stage` reports FAILED in every single run, successful or not** - it is racing the
controller's start-up, and it sometimes wins enough to move the arm partway (which is why the
pitch changes) but never enough to get its goal accepted.

By the time the approach is sent, the controller is up: **`unavailable` disappears and the
approach succeeds in the normal case.**

## Mode C is the other one

In the failing run the approach got a **`rejected`** - the controller was present and refused the
goal. That is H3: planned, IK-solved, and refused at the last step.

## What this fixes and what it does not

**Explains, cleanly:** why staging always reports failure, why the pitching still happens, and why
the approach normally succeeds. A one-time race is the simplest account and fits every observation.

**Does not explain:** why the controller refused the approach in that one run. `wait_for_server`
would have succeeded (otherwise the status would be `unavailable`), IK had a solution, planning
produced waypoints. The refusal happens between planning and the controller accepting the goal,
and **the code returns the status without recording the controller's reason.** That is a logging
gap, not a behaviour this round can resolve.

## The fix this suggests, not yet applied

Wait for the FollowJointTrajectory action server to be available **before** issuing the staging
move, rather than racing its start-up. That is a harness change in `t08_timeline.py` (already has
a `wait_for_server` for observe/push/move_to_pose, but that is the MoveToPose action, not the
controller action it forwards to).

**Untested. It would convert a constant silent failure into a real staging move, which changes
the starting pose the push gets - so it needs its own paired run and it must not be assumed to
improve anything.**

## Not claimed

- One `rejected` observed. Its cause is unknown.
- The race account of `unavailable` is the simplest explanation consistent with the data, not a
  directly measured one.
- T08 remains `CALIBRATION_UNSUPPORTED`.