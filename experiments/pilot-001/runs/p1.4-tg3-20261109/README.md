# P1.4 stage 2 — T-G3（regrasp 场景，真实 Gazebo，成功）

- 初始：`case=regrasp`, `place_pose=[0.45,0,0.0175]` → 探测得 `REGRASP_BLOCKED_FIRST_TASK / ERR_SKILL_FAILED`；
- deepseek-chat（FC agent）3 轮：`run_execution` → 读 telemetry/verdict → 写 `place_pose=[0.25,0]`；
- 独立验收：`gate/acceptance.py` 重跑真实 Gazebo（case=regrasp）→ `PASS`，指纹 `aa5ac497…`；
- 结果：**success=true，证据 1.0，false_success 0**。

## 意义
- 这是**第二类真实任务**（不同技能路径：regrasp），W1 的 M3-S 不再只是单一场景；
- 仍为 n=1；可靠性待重复验证。
