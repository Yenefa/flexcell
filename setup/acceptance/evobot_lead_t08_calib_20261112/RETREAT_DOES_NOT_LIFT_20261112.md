# THE MECHANISM, at the line: the retreat does not change height

`contracts/push.py:512-513`

```python
retreat = [face[0] - direction[0] * p['retreat_clearance_m'],
           face[1] - direction[1] * p['retreat_clearance_m'], face[2]]
```

**`face[2]` is carried through unchanged.** The retreat is horizontal: the arm moves back along
the reverse of the push direction at the same height it finished the push at.

`retreat_clearance_m` defaults to 0.03 and is a **distance**, not a lift. Raising it moves the
arm further back along the same height, not up out of the way.

## Why that produces the drag-back

The fingers sit **44.3 mm behind** the `end_effector_link` frame (established earlier this
session from the URDF). During the push the fingertips are at the box. When the arm retreats
horizontally, the frame moves back 0.03 - and the fingers, trailing behind it, sweep back
**through the space the box occupies**.

That is the ~0.06 m drag-back measured in rounds 64-66, and it is the same for every approach
geometry, which is exactly what the four-lever sweep found.

## Why no interface parameter fixes it

Every parameter available to me acts on the approach or on the push itself:

| parameter | where it acts | effect on the drag |
| --- | --- | --- |
| `contact_height_m` | height at contact | none measured; arithmetically bounded |
| `distance_m` | how far to push | drag scales with it |
| staging x, y | where the arm starts | drag unchanged near 0.06 |
| `retreat_clearance_m` | **how far** back, at the **same height** | cannot help - it is horizontal |

**None of them changes `face[2]`.**

## What the fix has to be

The retreat must gain height before it loses x. One line:

```python
retreat = [face[0] - direction[0] * p['retreat_clearance_m'],
           face[1] - direction[1] * p['retreat_clearance_m'],
           face[2] + p['retreat_lift_m']]
```

## And why I have not made it

**That line is in `contracts/push.py`, which `AUTHORITY_SCOPE.md` section 2 lists as a frozen
core contract that repository edits may not touch.**

`AUTHORITY_SCOPE.md` section 1 does authorise **isolated ROS 2 overlay builds and Gazebo
verification** - building a candidate in a separate workspace without touching the frozen file.
That route exists and was used before, for a different candidate.

**So the next step is an overlay that changes the retreat to gain height, tested alongside the
unmodified baseline on the same seeds.** That is the first change in this line that acts after
the push rather than before it, and it is falsifiable in the same way as the last four.

## Not claimed

- The lift is not implemented and not tested.
- The 0.06 m figure is an observation across four runs, not a constant.
- T08 remains `CALIBRATION_UNSUPPORTED`; no capability level is changed by this analysis.