# Carry-backend comparison (2026-11-18)

Why: after the #247 window showed a 5.2x placement spread, the read-only probe
(PR #271) measured the object offset in the gripper frame. It turned out that the
legacy backend moves the box by position only, with an identity orientation.

What is here:

- `compare.json` - the numbers in one place
- `velocity_servo/` - three window results plus one representative probe log
- `detachable/` - one window: two NORMAL passes, two DUAL failures, with probe logs

How to recompute:

```bash
python3 experiments/physical_capabilities/pick_place_reliability/analyze_windows.py \
  <window dir> ...
python3 experiments/physical_capabilities/carry_offset_probe/analyze_carry_offset.py \
  <window dir> ...
```

Boundaries: simulation only; `velocity_servo` landing n=6, `detachable_joint`
landing n=2; the detachable backend fails the DUAL case.
