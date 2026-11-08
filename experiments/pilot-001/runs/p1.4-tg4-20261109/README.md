# P1.4 — T-G4 组合任务（dual_object）可靠性 n=3

| rep | success | iters | tokens | zone_2_pose |
| --- | --- | --- | --- | --- |
| rep1 | true | 3 | 3432 | [0.2,0.05,0.0175] |
| rep2 | true | 3 | 3432 | [0.25,0.05,0.0175] |
| rep3 | true | 4 | 5698 | [0.2,0.15,0.0175] |

**3/3 成功**：每次都由 `gate/acceptance.py` 独立重跑真实 Gazebo（dual_object）判定；
agent 均把 `zone_2_pose` 从不可达 `[0.45,0.05,0.0175]` 改到可达值（0.20/0.25 等）。

## 边界
- 单任务族（组合）、单模型（deepseek-chat）；
- 初始失败确定（第二个对象落点不可达，A 已成功）；
- **M3-R 未达**。
