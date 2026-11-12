# T08 push defect — technical note for the owner of `contracts/push.py`

Written 2026-11-12 by the autonomous lead session. **Nothing in `contracts/push.py` was modified.** This note states
a measured defect precisely enough to act on, and states what is not established.

## One-line summary

`contact_height_m` is applied to the `end_effector_link` frame, but `end_effector_link` sits **44.3 mm in front of**
the finger joints. At the orientations actually used for a T08 push, that puts the **fingers 21.7 mm above the top
face of the box**, so no jaw face ever contacts a box side face. The commanded motion is a face push; the executed
motion is a friction drag across the top face.

## The geometry, read from `open_manipulator_x.urdf`

| Frame / joint | Parent | Offset |
| --- | --- | --- |
| `end_effector_joint` -> `end_effector_link` | `link5` | `xyz = (0.1260, 0, 0)` |
| `gripper_left_joint` | `link5` | `xyz = (0.0817, +0.0210, 0)` |
| `gripper_right_joint` | `link5` | `xyz = (0.0817, -0.0210, 0)` |

`end_effector_link` — the frame that `WorldState.robot.ee_pose` and the `move_to_pose` target both refer to — is
**0.1260 m** along `link5` `+x`. The finger joints are **0.0817 m** along the same axis. Therefore:

```
fingers sit 0.1260 - 0.0817 = 0.0443 m BEHIND the ee frame, along link5 -x
```

## What that does to `contact_height_m`

From an archived `move_to_pose` record of a real push approach (`evobot_lead_t08_height_offset_20261112`):

```
reached ee position  z = 0.0301
reached ee orientation q = [0.00394, 0.31715, -0.01179, 0.94829]
link5 x-axis in world  = (0.7985, -0.0199, -0.6016)
```

The fingers are displaced from the ee frame by `-0.0443 * link5_x`, so:

```
finger z = 0.0301 - 0.0443 * (-0.6016) = 0.0567
finger x =        +0.0443 * 0.7985    = +0.0354  (further +x than the ee frame)
```

Box geometry, from the T08 TaskSpec: 35 mm cube, `initial_pose z = 0.0175`, so centre **0.0175** and top **0.0350**.

**The fingers sit at z ~ 0.0567 — 21.7 mm above the box top — while the commanded `contact_height_m` of 0.0200
reads as if the contact point were at 0.0200.**

At full open travel (`lower = -0.011`, `upper = 0.02` in the URDF) the fingers remain 21 mm apart each side of
`link5` `+x`, and since the gripper is never commanded (`push_server.py` lines 20-26 state this explicitly, to keep
a push distinguishable from a carry), they simply straddle the box with clearance on both sides.

## Why this produces the observed failure statistics

| Observation | Explanation under this defect |
| --- | --- |
| **44% of single pushes reverse** (7/16, cosine ~ -1.000, `contact_made` True) | contact is top-face friction, which has no fixed direction |
| contact height 0.0150-0.0250 all produce BOTH outcomes | the 21.7 mm stand-off is large compared with the 10 mm scan range; every one of those heights is above the top face |
| approach pose accurate to 6 mm yet direction wrong | direction of a friction drag is not a function of the commanded pose |
| push 1 usually correct, push 2 often reversed | the descent from a neutral pose gets a glancing side contact before settling; a descent starting low beside the box lands squarely on top |
| camera: gripper body **above** the box, a jaw on each side | exactly what a 21.7 mm stand-off looks like |

## The two candidate fixes, both in `contracts/push.py`

1. **Make the TCP the finger midpoint.** Define the push contact frame as `link5 + (0.0817, 0, 0)` rather than
   `link5 + (0.126, 0, 0)`, and command `contact_height_m` against that frame. This is the cleaner fix: the
   parameter would then mean what its name says. Note this changes the meaning of every existing recorded target,
   so it needs a re-baseline.
2. **Compensate for the offset at the current frame.** Command the ee frame at
   `desired_contact_z + 0.0443 * (link5_x . z_hat)`, which is orientation-dependent and therefore must be computed
   per attempt rather than as a constant. With the orientation measured above that is `+0.0267 m`, so a requested
   contact height of 0.0200 would be commanded to the ee frame as ~0.0467.

I did not implement either. `contracts/push.py` is outside this session's granted scope, and both options change
a threshold-shaped quantity that this session is explicitly forbidden from tuning to make a test pass.

## What is established and what is not

**Established:** the URDF offsets (read from the file); the orientation and ee height (from an archived record); the
arithmetic above; the camera observation that the gripper arrives above the box; the 44% reversal rate and its
independence from contact height and request distance.

**Not established:** that compensating the offset *fixes* the task. That requires editing `push.py` and re-running,
which is the owner's call. Also not established is that the orientation used in the calculation is representative —
it is one archived record, not a distribution.

## Evidence locations

- Camera frames: `reversal_visual_20261112/` (`controlled_correct_push2.png`, `controlled_reversed_push2.png`)
- Reversal statistics: 16 single-shot pushes over 4 request distances, committed this session
- Single-shot pass rate: 0/10 at request 0.10; 7/16 across request 0.04-0.09
- Gripper design intent: `push_server.py` lines 20-26
