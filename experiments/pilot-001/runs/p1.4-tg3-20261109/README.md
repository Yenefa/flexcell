# P1.4 stage 2 — T-G3（regrasp 真实 Gazebo）可靠性 n=3

| rep | success | iters | tokens | 证据完整度 |
| --- | --- | --- | --- | --- |
| rep1 | true | 3 | 3574 | 1 |
| rep2 | true | 3 | 3556 | 1 |
| rep3 | true | 3 | 3516 | 1 |

**3/3 成功**，均 3 轮、约 3.5k tokens；每次都由 `gate/acceptance.py` 独立重跑真实 Gazebo（case=regrasp）判定。

## 边界
- 单任务族（regrasp）+ 单模型（deepseek-chat）；
- 初始失败确定（`place_pose=0.45` 不可达）；
- **M3-R 未达**（真实机器人）。
