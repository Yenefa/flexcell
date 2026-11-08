# P1.4 stage 2 — T-G1 脚本化 agent 真实 Gazebo 全链路（成功）

- 脚本化 agent：写 `plan.json` 的 `place_pose=[0.20,0,0.0175]` → `run_execution`（真实 Gazebo）→ judge 独立再跑一次真实 Gazebo。
- 结果：**success=true**，1 轮，证据完整度 **1.0**，verdict **PASS**。
- 这是"Agent 修改参数 → 真实执行 → 独立验证 → 完整证据"的**管道级 M3-S**（脚本 agent，非 LLM）。

## LLM（deepseek-chat）同任务记录
- 会调用 `run_execution`、读 telemetry/verdict、会写 `plan.json`；
- 但数值不稳定：曾写 `0.30`（本应 PASS，被 HashGuard 空列表 bug 误判）、随后写 `0.35`（超限失败）；
- 判定：**LLM 可靠性不足（BLOCKED）**，不作 W1 M3-S 依据。
