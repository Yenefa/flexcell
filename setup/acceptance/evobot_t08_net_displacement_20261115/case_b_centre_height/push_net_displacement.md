# Push progress vs net displacement

Task outcome: **not evaluated by this tool** (diagnostic facts only).

Direction (unit, planar): (-1.000000, 0.000000)

| # | report | requested m | reported progress m | recomputed m | poses |
| - | - | - | - | - | - |
| 0 | push_00.json | 0.090000 | 0.105670 | 0.105670 | yes |

## Quantities

- **Progress**: 0.105670 m
- **Net displacement**: 0.105670 m
- **Difference (net - progress)**: 0.000000 m

Definitions:
- progress_m: sum of the per-report displacement_along_direction_m
- net_m: signed projection of (last measured_after - first measured_before) on the task direction
- difference_m: net_m - progress_m; non-zero means the reports do not partition the motion
