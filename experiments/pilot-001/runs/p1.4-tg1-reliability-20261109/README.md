# P1.4 stage 2 — T-G1 可靠性（真实 Gazebo，deepseek-chat）

| rep | success | 轮数 | tokens | 证据 | 写入 pose |
| --- | --- | --- | --- | --- | --- |
| rep1 | true | 3 | 3532 | 1 | [0.25,0,0.0175] |
| rep2 | true | 3 | 3505 | 1 | [0.25,0,0.0175] |
| rep3 | true | 3 | 3512 | 1 | [0.25,0,0.0175] |

**3/3 成功**，均为 3 轮、约 3.5k tokens、证据 1.0；每轮都由 `gate/acceptance.py` 独立重跑真实 Gazebo 判定。

## 边界
- 单任务（T-G1）、单模型（deepseek-chat）、n=3；
- telemetry 含 `limits.max_reach_m`（能力规格）；
- 不代表多任务/多模型泛化，也不代表真实机器人（M3-R 未达）。
