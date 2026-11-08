# P1.4 stage 2 — T-G1 LLM 成功（deepseek-chat，真实 Gazebo）

- 模型：`deepseek-chat`，FC agent，3 轮；
- 过程：run_execution（看到 `ROBOT_FAILURE` + limits）→ 读 telemetry/verdict → 写 `place_pose=[0.25,0,0.0175]`；
- 验收：`gate/acceptance.py` **独立再跑真实 Gazebo** → `PASS`，指纹 `aa5ac497…`；
- 结果：**success=true，证据完整度 1.0，false_success 0**。

## 说明
- 本轮在 telemetry 中增加了机器可读约束 `limits.max_reach_m=0.30`（能力规格，不是答案）；此前 LLM 数值选择不稳定。
- 这是 **W1 M3-S 证据**（单任务、单模型、n=1），不代表可靠性已达标。
