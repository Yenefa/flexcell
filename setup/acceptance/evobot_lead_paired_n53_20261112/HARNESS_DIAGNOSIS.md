# Harness diagnosis: rclpy node creation fails — three fixes tried, none worked

**Date** 2026-11-12 (round 24) · **Status: UNRESOLVED. Gazebo work remains blocked.**

## The fault

```
rclpy._rclpy_pybind11.RCLError: error creating node: error not set, at ./src/rcl/node.c:252
```

Deterministic, single trial, clean environment, fresh domain, 8 occurrences per stack start (round 23).

## Tests run (each isolated, fresh ROS_DOMAIN_ID)

| test | result |
| --- | --- |
| A. `rclpy.create_node()` as-is, domain 260 | **FAIL** |
| B. `ROS_LOCALHOST_ONLY=1`, domain 261 | **FAIL** |
| C. after `hostnamectl set-hostname rosbox` + `/etc/hosts` fix, domain 262 | **FAIL** |

So it is **not** hostname resolution, **not** localhost-only discovery, and **not** the abnormal
`hostname == localhost` (which resolved to `::1` via getent while Python resolved `127.0.0.1` — a real
inconsistency, but not the cause).

**The hostname change was reverted** because it fixed nothing; leaving the environment as found is safer than
leaving it altered for no gain.

## What is still untested

- whether the `rcl`/`rmw` install itself is intact (e.g. a broken `rmw_cyclonedds_cpp` build or a missing
  `librmw` symbol) — removing the middleware entirely is the next step
- whether the RMW falls back to a working implementation at all
- whether the fault is in CycloneDDS config (`CYCLONEDDS_URI`) rather than in rcl

## Consequence

**Every remaining robotics phase is blocked** until this is repaired: the pre-registered paired experiment
cannot run, no T08 measurement can be taken, no fresh unseen batch can be generated. The registered design is
unchanged and still binding.