# Push progress vs net displacement

Task outcome: **not evaluated by this tool** (diagnostic facts only).

Direction (unit, planar): (-1.000000, 0.000000)

| # | report | requested m | reported progress m | recomputed m | poses |
| - | - | - | - | - | - |
| 0 | push_00.json | 0.090000 | 0.022806 | n/a | missing |
| 1 | push_01.json | 0.067194 | -0.026181 | n/a | missing |

## Quantities

- **Progress**: UNKNOWN - attempts were requested along different directions; their sum is not a displacement
- **Net displacement**: UNKNOWN - the first report has no usable measured_before; the last report has no usable measured_after
- **Difference (net - progress)**: UNKNOWN - progress is unknown; net displacement is unknown

Definitions:
- progress_m: sum of the per-report displacement_along_direction_m
- net_m: signed projection of (last measured_after - first measured_before) on the task direction
- difference_m: net_m - progress_m; non-zero means the reports do not partition the motion
